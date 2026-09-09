use std::env;
use std::fs;
use std::io;
use std::io::prelude::*;
use tracing_subscriber::prelude::*;

const USAGE: &str = "Usage: average <input.json>";
const EARTH_RADIUS: f64 = 6372.8;

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Debug, Clone, Copy)]
struct Pair {
    x0: f64,
    y0: f64,
    x1: f64,
    y1: f64,
}

enum Key {
    X0,
    Y0,
    X1,
    Y1,
}

struct Cursor<'a, R: BufRead> {
    reader: &'a mut R,
    offset: usize,
}

impl<R: BufRead> Cursor<'_, R> {
    fn new<'a>(reader: &'a mut R) -> Cursor<'a, R> {
        Cursor { reader, offset: 0 }
    }

    fn peek(&mut self) -> Result<Option<u8>> {
        let buf = self.reader.fill_buf()?;
        Ok(buf.first().copied())
    }

    fn peek_non_whitespace(&mut self) -> Result<Option<u8>> {
        self.skip_whitespace()?;
        self.peek()
    }

    fn advance(&mut self) -> Result<()> {
        let buf = self.reader.fill_buf()?;
        if buf.is_empty() {
            Err(format!(
                "Attempted to advance past the end of the string at position {}",
                self.offset,
            )
            .into())
        } else {
            self.reader.consume(1);
            self.offset += 1;
            Ok(())
        }
    }

    fn skip_whitespace(&mut self) -> Result<()> {
        loop {
            let (consumed, finished) = {
                let buf = self.reader.fill_buf()?;
                let mut consumed = 0;

                for &b in buf {
                    match b {
                        b' ' | b'\t' | b'\n' | b'\r' => consumed += 1,
                        _ => break,
                    }
                }
                let finished = buf.is_empty() || consumed < buf.len();
                (consumed, finished)
            };
            self.reader.consume(consumed);
            if finished {
                return Ok(());
            }
        }
    }

    fn expect(&mut self, expected: u8) -> Result<()> {
        let actual = self.peek()?;
        if let Some(actual) = actual {
            if actual == expected {
                self.advance()?;
                Ok(())
            } else {
                Err(format!(
                    "Expected {expected}, got {actual} at position {}",
                    self.offset
                )
                .into())
            }
        } else {
            Err(format!(
                "Expected {expected} but reached end of string at position {}",
                self.offset
            )
            .into())
        }
    }
}

/**
 * Compute each distance and return the mean in kilometers.
 * Use radius 6372.8 and the reference formula in generate.rs (fn haversine).
 * Decide how to handle an empty array; do not silently report a zero mean.
 */
fn average_haversine<R: BufRead>(cursor: &mut Cursor<'_, R>) -> Result<(f64, usize)> {
    let _average = tracing::info_span!("average_haversine").entered();
    // Sample JSON
    // {"pairs":[
    //   {"x0":40.56278926715536,"y0":-38.05685214827928,"x1":58.67978065278559,"y1":-42.10090404776115},
    //   {"x0":-56.6345357859396,"y0":23.104742585733618,"x1":-45.4156347086755,"y1":-5.019891497482234}
    // ]}

    cursor.skip_whitespace()?;
    cursor.expect(b'{')?;

    cursor.skip_whitespace()?;
    for &expected in b"\"pairs\"" {
        cursor.expect(expected)?
    }

    cursor.skip_whitespace()?;
    cursor.expect(b':')?;

    cursor.skip_whitespace()?;
    cursor.expect(b'[')?;

    let mut sum: f64 = 0.0;
    let mut count: usize = 0;
    // One span per 10,000 pairs avoids per-byte/per-pair tracing overhead.
    let mut batch = None;

    if cursor.peek_non_whitespace()? != Some(b']') {
        loop {
            if count % 10_000 == 0 {
                batch = Some(
                    tracing::info_span!(
                        "parse_and_average_batch",
                        first_pair = count,
                        byte_offset = cursor.offset
                    )
                    .entered(),
                );
            }
            let pair = parse_pair(cursor)?;
            sum += reference_haversine(&pair, EARTH_RADIUS);
            count += 1;
            if count % 10_000 == 0 {
                drop(batch.take());
            }

            match cursor.peek_non_whitespace()? {
                Some(b']') => break,
                Some(b',') => cursor.advance()?,
                _ => return Err(format!("Expected ',' or ']' at offset {}", cursor.offset).into()),
            }
        }
    }

    drop(batch);
    cursor.skip_whitespace()?;
    cursor.expect(b']')?;
    cursor.skip_whitespace()?;
    cursor.expect(b'}')?;
    cursor.skip_whitespace()?;

    if let Some(b) = cursor.peek()? {
        Err(format!(
            "Expected EOF; got unexpected character {b} at offset {}",
            cursor.offset
        )
        .into())
    } else if count == 0 {
        Err("Got a 0-element array, no average is possible!".into())
    } else {
        Ok((sum / count as f64, count))
    }
}

fn parse_pair<R: BufRead>(cursor: &mut Cursor<'_, R>) -> Result<Pair> {
    let mut x0 = None;
    let mut y0 = None;
    let mut x1 = None;
    let mut y1 = None;

    cursor.skip_whitespace()?;
    cursor.expect(b'{')?;
    if cursor.peek_non_whitespace()? != Some(b'}') {
        loop {
            let (key, value) = parse_field(cursor)?;
            match key {
                Key::X0 => x0 = Some(value),
                Key::Y0 => y0 = Some(value),
                Key::X1 => x1 = Some(value),
                Key::Y1 => y1 = Some(value),
            }

            match cursor.peek_non_whitespace()? {
                Some(b',') => cursor.advance()?,
                Some(b'}') => {
                    cursor.advance()?;
                    break;
                }
                _ => return Err(format!("Expected ',' or '}}' at offset {}", cursor.offset).into()),
            }
        }
    }

    if let Some(x0) = x0
        && let Some(y0) = y0
        && let Some(x1) = x1
        && let Some(y1) = y1
    {
        Ok(Pair { x0, y0, x1, y1 })
    } else {
        Err(format!("Couldn't find all of x0, y0, x1, and y1").into())
    }
}

fn parse_field<R: BufRead>(cursor: &mut Cursor<'_, R>) -> Result<(Key, f64)> {
    let key = parse_key(cursor)?;
    cursor.skip_whitespace()?;
    cursor.expect(b':')?;
    cursor.skip_whitespace()?;
    let val = parse_val(cursor)?;
    Ok((key, val))
}

fn parse_key<R: BufRead>(cursor: &mut Cursor<'_, R>) -> Result<Key> {
    cursor.skip_whitespace()?;
    cursor.expect(b'"')?;
    if let Some(x_or_y) = cursor.peek()? {
        cursor.advance()?;
        if let Some(zero_or_one) = cursor.peek()? {
            cursor.advance()?;
            cursor.expect(b'"')?;
            return match (x_or_y, zero_or_one) {
                (b'x', b'0') => Ok(Key::X0),
                (b'y', b'0') => Ok(Key::Y0),
                (b'x', b'1') => Ok(Key::X1),
                (b'y', b'1') => Ok(Key::Y1),
                _ => Err(format!(
                    "Unexpected characters {x_or_y}{zero_or_one} at offset {}",
                    cursor.offset
                )
                .into()),
            };
        }
    }
    Err(format!("Couldn't find a string key at offset {}", cursor.offset).into())
}

fn parse_val<R: BufRead>(cursor: &mut Cursor<'_, R>) -> Result<f64> {
    let (sign, mut value) = parse_integer(cursor)?;

    if cursor.peek()? == Some(b'.') {
        cursor.advance()?;

        let mut frac_pow = 1.0;

        loop {
            let (consumed, number_ended) = {
                let buf = cursor.reader.fill_buf()?;
                let mut consumed = 0;

                for &b in buf {
                    if !b.is_ascii_digit() {
                        break;
                    }

                    frac_pow *= 0.1;
                    value += frac_pow * (b - b'0') as f64;
                    consumed += 1;
                }

                let number_ended = consumed < buf.len() || buf.is_empty();
                (consumed, number_ended)
            };

            cursor.reader.consume(consumed);
            cursor.offset += consumed;

            if number_ended {
                break;
            }
        }
    }

    match cursor.peek()? {
        Some(b'e' | b'E') => {
            cursor.advance()?;
            if cursor.peek()? == Some(b'+') {
                cursor.advance()?;
            }
            let (exp_sign, exp) = parse_integer(cursor)?;
            value *= 10.0_f64.powf(exp_sign * exp);
        }
        _ => {}
    }
    Ok(sign * value)
}

fn parse_integer<R: BufRead>(cursor: &mut Cursor<'_, R>) -> Result<(f64, f64)> {
    let mut sign = 1.0;
    let mut value = 0.0;

    if cursor.peek()? == Some(b'-') {
        sign = -1.0;
        cursor.advance()?;
    }

    let mut seen_digits = false;

    loop {
        let (consumed, number_ended) = {
            let buf = cursor.reader.fill_buf()?;
            let mut consumed = 0;

            for &b in buf {
                if !b.is_ascii_digit() {
                    break;
                }

                seen_digits = true;
                value *= 10.0;
                value += (b - b'0') as f64;
                consumed += 1;
            }

            let number_ended = consumed < buf.len() || buf.is_empty();
            (consumed, number_ended)
        };

        cursor.reader.consume(consumed);
        cursor.offset += consumed;

        if number_ended {
            break;
        }
    }

    if seen_digits {
        Ok((sign, value))
    } else {
        Err(format!("Expected a number at offset {}", cursor.offset).into())
    }
}

// NOTE(casey): EarthRadius is generally expected to be 6372.8
fn reference_haversine(pair: &Pair, radius: f64) -> f64 {
    /* NOTE(casey): This is not meant to be a "good" way to calculate the Haversine distance.
       Instead, it attempts to follow, as closely as possible, the formula used in the real-world
       question on which these homework exercises are loosely based.
    */

    let mut lat1 = pair.y0;
    let mut lat2 = pair.y1;
    let lng1 = pair.x0;
    let lng2 = pair.x1;

    let d_lat = radians_from_degrees(lat2 - lat1);
    let d_lng = radians_from_degrees(lng2 - lng1);

    lat1 = radians_from_degrees(lat1);
    lat2 = radians_from_degrees(lat2);

    let a = square((d_lat / 2.0).sin()) + lat1.cos() * lat2.cos() * square((d_lng / 2.0).sin());
    let c = 2.0 * a.sqrt().asin();

    return radius * c;
}

fn square(a: f64) -> f64 {
    return a * a;
}

fn radians_from_degrees(degrees: f64) -> f64 {
    return 0.01745329251994329577 * degrees;
}

fn run() -> Result<()> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    if args.len() == 1 && (args[0] == "--help" || args[0] == "-h") {
        println!("{USAGE}");
        return Ok(());
    }
    if args.len() != 1 {
        return Err(USAGE.into());
    }

    // Keep the flush guard alive until all spans have closed, including on errors.
    let _trace_guard = if let Some(path) = env::var_os("HAVERSINE_TRACE") {
        let file = fs::File::create_new(&path)?;
        let (layer, guard) = tracing_chrome::ChromeLayerBuilder::new()
            .writer(io::BufWriter::new(file))
            .include_args(true)
            .include_locations(false)
            .build();
        tracing_subscriber::registry().with(layer).try_init()?;
        eprintln!("Writing trace to {}", std::path::Path::new(&path).display());
        Some(guard)
    } else {
        None
    };
    let _run = tracing::info_span!("haversine_run").entered();
    let f = {
        let _open = tracing::info_span!("open_input").entered();
        fs::File::open(&args[0])?
    };
    let mut reader = io::BufReader::new(f);
    let mut cursor = Cursor::new(&mut reader);
    let (mean, pair_count) = average_haversine(&mut cursor)?;
    println!("Pair count: {pair_count}\nMean Haversine distance: {mean:.16} km",);
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("Error: {error}");
        std::process::exit(1);
    }
}
