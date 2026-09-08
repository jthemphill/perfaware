//! Streaming, reproducible inputs for the Haversine distance exercise.

use std::env;
use std::fs::{self, File};
use std::io::{self, BufWriter, Write};
use std::path::PathBuf;

const EARTH_RADIUS: f64 = 6372.8;
const CLUSTERS: u64 = 64;
const USAGE: &str =
    "Usage: generate <uniform|cluster> <seed:u64> <pairs:positive-u64> [output-directory]";

// SplitMix64: fixed algorithm so a seed reproduces the same coordinates.
// This is a test-data PRNG, not a cryptographic random source.
struct Random(u64);

impl Random {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e3779b97f4a7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
        z ^ (z >> 31)
    }

    fn range(&mut self, min: f64, max: f64) -> f64 {
        let unit = (self.next() >> 11) as f64 / ((1u64 << 53) as f64);
        min + (max - min) * unit
    }
}

#[derive(Clone, Copy, Debug)]
struct Region {
    x_min: f64,
    x_max: f64,
    y_min: f64,
    y_max: f64,
}

impl Region {
    const WORLD: Self = Self {
        x_min: -180.0,
        x_max: 180.0,
        y_min: -90.0,
        y_max: 90.0,
    };

    fn random(rng: &mut Random) -> Self {
        let x = rng.range(-180.0, 180.0);
        let y = rng.range(-90.0, 90.0);
        let x_radius = rng.range(0.1, 180.0);
        let y_radius = rng.range(0.1, 90.0);
        Self {
            x_min: (x - x_radius).max(-180.0),
            x_max: (x + x_radius).min(180.0),
            y_min: (y - y_radius).max(-90.0),
            y_max: (y + y_radius).min(90.0),
        }
    }

    fn pair(self, rng: &mut Random) -> [f64; 4] {
        [
            rng.range(self.x_min, self.x_max),
            rng.range(self.y_min, self.y_max),
            rng.range(self.x_min, self.x_max),
            rng.range(self.y_min, self.y_max),
        ]
    }
}

fn haversine([x0, y0, x1, y1]: [f64; 4]) -> f64 {
    let d_lat = (y1 - y0).to_radians();
    let d_lon = (x1 - x0).to_radians();
    let a = (d_lat / 2.0).sin().powi(2)
        + y0.to_radians().cos() * y1.to_radians().cos() * (d_lon / 2.0).sin().powi(2);
    // Rounding can put an antipodal pair just outside asin's domain.
    2.0 * EARTH_RADIUS * a.clamp(0.0, 1.0).sqrt().asin()
}

fn generate(
    json: &mut impl Write,
    answers: &mut impl Write,
    clustered: bool,
    seed: u64,
    count: u64,
) -> io::Result<f64> {
    if count == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "pair count must be positive",
        ));
    }
    let mut rng = Random(seed);
    let groups = if clustered { CLUSTERS.min(count) } else { 1 };
    let mut written = 0;
    let mut sum = 0.0;
    let mut correction = 0.0;
    writeln!(json, "{{\"pairs\":[")?;
    for group in 0..groups {
        let region = if clustered {
            Region::random(&mut rng)
        } else {
            Region::WORLD
        };
        let group_size = count / groups + u64::from(group < count % groups);
        for _ in 0..group_size {
            let pair @ [x0, y0, x1, y1] = region.pair(&mut rng);
            let distance = haversine(pair);
            // Kahan summation limits accumulation error on very large inputs.
            let adjusted = distance - correction;
            let next = sum + adjusted;
            correction = (next - sum) - adjusted;
            sum = next;
            written += 1;
            let comma = if written == count { "" } else { "," };
            // Display emits round-trippable f64 decimal representations.
            writeln!(
                json,
                "  {{\"x0\":{x0},\"y0\":{y0},\"x1\":{x1},\"y1\":{y1}}}{comma}"
            )?;
            answers.write_all(&distance.to_le_bytes())?;
        }
    }
    writeln!(json, "]}}")?;
    let mean = sum / count as f64;
    answers.write_all(&mean.to_le_bytes())?;
    json.flush()?;
    answers.flush()?;
    Ok(mean)
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len() == 1 && matches!(args[0].as_str(), "--help" | "-h") {
        println!("{USAGE}");
        return Ok(());
    }
    if !(3..=4).contains(&args.len()) {
        return Err(USAGE.into());
    }
    let clustered = match args[0].as_str() {
        "cluster" => true,
        "uniform" => false,
        _ => return Err(USAGE.into()),
    };
    let seed: u64 = args[1]
        .parse()
        .map_err(|_| "seed must be an unsigned 64-bit integer")?;
    let count: u64 = args[2]
        .parse()
        .map_err(|_| "pair count must be a positive 64-bit integer")?;
    if count == 0 {
        return Err("pair count must be positive (the mean of zero pairs is undefined)".into());
    }
    let output = args
        .get(3)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../build/part2"));
    fs::create_dir_all(&output)?;
    let stem = format!("data_{}_{}_{}", args[0], seed, count);
    let json_path = output.join(format!("{stem}.json"));
    let answers_path = output.join(format!("{stem}.f64"));
    let mut json = BufWriter::new(File::create(&json_path)?);
    let mut answers = BufWriter::new(File::create(&answers_path)?);
    let mean = generate(&mut json, &mut answers, clustered, seed, count)?;
    println!(
        "Method: {}\nRandom seed: {seed}\nPair count: {count}\nExpected mean: {mean:.16}",
        args[0]
    );
    println!(
        "JSON: {}\nAnswers: {}",
        json_path.display(),
        answers_path.display()
    );
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("Error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_distances() {
        assert_eq!(haversine([12.0, 34.0, 12.0, 34.0]), 0.0);
        let half = std::f64::consts::PI * EARTH_RADIUS;
        assert!((haversine([0.0, 0.0, 180.0, 0.0]) - half).abs() < 1e-9);
        assert!((haversine([0.0, 0.0, 90.0, 0.0]) - half / 2.0).abs() < 1e-9);
    }

    #[test]
    fn counts_and_reference_mean() {
        for clustered in [false, true] {
            for count in [1, 10, 63, 64, 65, 129] {
                let (mut json, mut answers) = (Vec::new(), Vec::new());
                let mean = generate(&mut json, &mut answers, clustered, 42, count).unwrap();
                assert_eq!(answers.len(), (count as usize + 1) * 8);
                let values: Vec<f64> = answers
                    .chunks_exact(8)
                    .map(|b| f64::from_le_bytes(b.try_into().unwrap()))
                    .collect();
                assert_eq!(values[count as usize], mean);
                assert!(
                    (values[..count as usize].iter().sum::<f64>() / count as f64 - mean).abs()
                        < 1e-9
                );
                let text = String::from_utf8(json).unwrap();
                assert_eq!(text.matches("\"x0\"").count(), count as usize);
                assert!(text.ends_with("}\n]}\n"));
            }
        }
    }

    #[test]
    fn coordinates_stay_in_region_and_world() {
        let mut rng = Random(123);
        for _ in 0..1000 {
            let region = Region::random(&mut rng);
            let [x0, y0, x1, y1] = region.pair(&mut rng);
            for x in [x0, x1] {
                assert!((-180.0..=180.0).contains(&x));
                assert!((region.x_min..=region.x_max).contains(&x));
            }
            for y in [y0, y1] {
                assert!((-90.0..=90.0).contains(&y));
                assert!((region.y_min..=region.y_max).contains(&y));
            }
        }
    }

    #[test]
    fn reproducible_but_seed_sensitive() {
        let output = |seed| {
            let (mut json, mut answers) = (Vec::new(), Vec::new());
            generate(&mut json, &mut answers, true, seed, 100).unwrap();
            (json, answers)
        };
        assert_eq!(output(42), output(42));
        assert_ne!(output(42), output(43));
    }

    #[test]
    fn empty_input_rejected() {
        assert!(generate(&mut Vec::new(), &mut Vec::new(), true, 0, 0).is_err());
    }
}
