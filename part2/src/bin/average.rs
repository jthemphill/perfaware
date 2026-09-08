//! Exercise scaffold: hand-written JSON parsing and average Haversine distance.

use std::env;
use std::fs;

const USAGE: &str = "Usage: average <input.json>";

#[derive(Debug, Clone, Copy)]
#[allow(dead_code)] // Remove once the averaging implementation reads these fields.
struct Pair {
    x0: f64,
    y0: f64,
    x1: f64,
    y1: f64,
}

fn parse_pairs(_input: &[u8]) -> Result<Vec<Pair>, String> {
    // TODO: Write your parser here, starting with a byte cursor into input.
    // Expected shape: {"pairs":[{"x0":...,"y0":...,"x1":...,"y1":...}, ...]}
    // Handle whitespace, punctuation, field names, and JSON numbers yourself.
    // Report malformed input with its byte offset, and reject trailing content.
    // No JSON library is included; the parser design is yours.
    Err("parse_pairs is not implemented yet".into())
}

fn average_haversine(_pairs: &[Pair]) -> Result<f64, String> {
    // TODO: Compute each distance and return the mean in kilometers.
    // Use radius 6372.8 and the reference formula in generate.rs (fn haversine).
    // Decide how to handle an empty array; do not silently report a zero mean.
    Err("average_haversine is not implemented yet".into())
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args_os().skip(1).collect();
    if args.len() == 1 && (args[0] == "--help" || args[0] == "-h") {
        println!("{USAGE}");
        return Ok(());
    }
    if args.len() != 1 {
        return Err(USAGE.into());
    }

    let input = fs::read(&args[0])?;
    let pairs = parse_pairs(&input)?;
    let mean = average_haversine(&pairs)?;
    println!(
        "Pair count: {}\nMean Haversine distance: {mean:.16} km",
        pairs.len()
    );
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("Error: {error}");
        std::process::exit(1);
    }
}
