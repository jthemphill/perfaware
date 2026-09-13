//! Architecture-selected hardware counters: opaque ticks and ticks per second.

#[cfg_attr(
    all(not(feature = "portable-timer"), target_arch = "x86_64"),
    path = "x86.rs"
)]
#[cfg_attr(
    all(not(feature = "portable-timer"), target_arch = "aarch64"),
    path = "aarch64.rs"
)]
#[cfg_attr(
    any(
        feature = "portable-timer",
        not(any(target_arch = "x86_64", target_arch = "aarch64"))
    ),
    path = "portable.rs"
)]
mod backend;

pub use backend::{read_ticks, timer_frequency_hz, timer_name};

/// Calibrate counters whose frequency is not reported by the platform.
pub fn estimate_timer_frequency_hz() -> u64 {
    const DURATION: std::time::Duration = std::time::Duration::from_millis(100);
    let start_time = std::time::Instant::now();
    let start_ticks = read_ticks();
    while start_time.elapsed() < DURATION {
        std::hint::spin_loop();
    }
    let elapsed_ticks = read_ticks().wrapping_sub(start_ticks);
    (elapsed_ticks as f64 / start_time.elapsed().as_secs_f64()) as u64
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{Duration, Instant};

    #[test]
    fn frequency_fallback_measures_a_nonzero_interval() {
        let start = Instant::now();
        let frequency = estimate_timer_frequency_hz();
        assert!(start.elapsed() >= Duration::from_millis(100));
        assert!(frequency > 0);
    }

    #[test]
    fn ticks_and_frequency_agree_with_elapsed_time() {
        let frequency = timer_frequency_hz().unwrap_or_else(estimate_timer_frequency_hz);
        assert!(frequency > 0);
        let start_time = Instant::now();
        let start = read_ticks();
        std::thread::sleep(Duration::from_millis(30));
        let ticks = read_ticks().wrapping_sub(start);
        let seconds = ticks as f64 / frequency as f64;
        let elapsed = start_time.elapsed().as_secs_f64();
        // Broad tolerance for scheduler delays and calibration in VMs;
        // still catches mismatched units or a wrong platform timebase.
        assert!(ticks > 0);
        assert!(
            (seconds - elapsed).abs() < elapsed * 0.25 + 0.005,
            "{}: counter={seconds}s, Instant={elapsed}s",
            timer_name()
        );
    }
}
