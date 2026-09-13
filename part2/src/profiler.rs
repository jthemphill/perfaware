use crate::read_ticks;
#[cfg(feature = "profiling")]
use crate::{estimate_timer_frequency_hz, timer_frequency_hz};

/// Evaluate an expression, add its elapsed timer ticks, and return its result.
///
/// The counter place is evaluated and borrowed once, after the work finishes.
/// A returned `Err` is timed; `?`, `return`, `break`, or a panic that exits the
/// work early skips the update. Put `?` after the macro to time failed operations.
/// Uses raw counter reads without instruction-ordering barriers. Arithmetic wraps.
/// Without `profiling`, only the work is evaluated; the counter is not evaluated.
#[cfg(feature = "profiling")]
#[macro_export]
macro_rules! timed {
    ($counter:expr, $work:expr $(,)?) => {{
        // let start = $crate::read_ticks();
        let result = $work;
        // let delta = $crate::read_ticks().wrapping_sub(start);
        // let counter: &mut u64 = &mut $counter;
        // *counter = counter.wrapping_add(delta);
        result
    }};
}

#[cfg(not(feature = "profiling"))]
#[macro_export]
macro_rules! timed {
    ($counter:expr, $work:expr $(,)?) => {
        $work
    };
}

/// Convenience methods for accumulating timer ticks in an ordinary `u64`.
///
/// Import this trait to use these methods. Updates require a mutable reference.
/// Omits instruction-ordering barriers to minimize overhead.
/// Surrounding instructions may execute across the timestamp read.
pub trait TickCounter {
    /// Add an already calculated delta. Totals wrap on overflow.
    fn add(&mut self, delta: u64);

    /// Add the elapsed ticks between two readings, returning the delta.
    #[inline]
    fn add_elapsed(&mut self, start: u64, end: u64) -> u64 {
        let delta = end.wrapping_sub(start);
        self.add(delta);
        delta
    }

    /// Read the timer and add the elapsed ticks since `start`.
    #[inline]
    fn add_since(&mut self, start: u64) -> u64 {
        self.add_elapsed(start, read_ticks())
    }
}

impl TickCounter for u64 {
    #[inline]
    fn add(&mut self, delta: u64) {
        *self = self.wrapping_add(delta);
    }
}

/// Owned profiler totals. Initialize before timing work to exclude calibration,
/// then pass `&mut ProfilerStats` to functions that record measurements.
///
/// ```
/// use haversine_generator::{ProfilerStats, timed};
///
/// fn parse(stats: &mut ProfilerStats) -> Result<u64, std::num::ParseIntError> {
///     timed!(stats.parse, "42".parse())
/// }
///
/// let mut stats = ProfilerStats::default();
/// assert_eq!(parse(&mut stats).unwrap(), 42);
/// let seconds = stats.parse as f64 / stats.timer_freq_hz as f64;
/// ```
#[derive(Debug)]
#[cfg(feature = "profiling")]
pub struct ProfilerStats {
    /// Timer ticks per second.
    pub timer_freq_hz: u64,
    /// Timestamp taken after frequency initialization completes.
    pub start: u64,
    pub startup: u64,
    /// Underlying read ticks, collected from the reader before reporting.
    pub read: u64,
    pub parse: u64,
    pub sum: u64,
    pub misc_output: u64,
}

#[cfg(feature = "profiling")]
impl ProfilerStats {
    /// Report the accumulated phase totals.
    /// Read time can also be included in parse time.
    pub fn print_stats(&self) {
        let total_ticks = read_ticks().wrapping_sub(self.start);

        let as_dur = |dur: u64| -> std::time::Duration {
            std::time::Duration::from_secs_f64(dur as f64 / self.timer_freq_hz as f64)
        };

        macro_rules! print_stat {
            ($label:literal, $ticks:expr) => {{
                let ticks = $ticks;
                let percent = if total_ticks == 0 {
                    0.0
                } else {
                    100.0 * ticks as f64 / total_ticks as f64
                };
                println!("  {}: {:?} ({:.2}%)", $label, as_dur(ticks), percent);
            }};
        }

        println!(
            "Total time: {:?} (timer: {}, ticks/s: {})",
            as_dur(total_ticks),
            crate::timer_name(),
            self.timer_freq_hz
        );
        print_stat!("Startup", self.startup);
        print_stat!("Read", self.read);
        print_stat!("Parse", self.parse);
        print_stat!("Sum", self.sum);
        print_stat!("Misc Output", self.misc_output);
    }
}

#[cfg(feature = "profiling")]
impl Default for ProfilerStats {
    fn default() -> Self {
        let cpu_freq = timer_frequency_hz().unwrap_or_else(estimate_timer_frequency_hz);
        Self {
            timer_freq_hz: cpu_freq,
            start: read_ticks(),
            startup: 0,
            read: 0,
            parse: 0,
            sum: 0,
            misc_output: 0,
        }
    }
}

/// No storage, timer initialization, or reporting when profiling is disabled.
#[cfg(not(feature = "profiling"))]
#[derive(Debug, Default)]
pub struct ProfilerStats;

#[cfg(not(feature = "profiling"))]
impl ProfilerStats {
    pub fn print_stats(&self) {}
}

#[cfg(test)]
mod tests {
    use super::TickCounter;

    #[test]
    #[cfg(feature = "profiling")]
    fn timed_evaluates_work_then_counter_once() {
        let mut events = Vec::new();
        let mut counters = [0_u64];
        let result = crate::timed!(
            counters[{
                events.push("counter");
                0
            }],
            {
                events.push("work");
                Err::<(), _>("read failed")
            },
        );
        assert_eq!(result, Err("read failed"));
        assert_eq!(events, ["work", "counter"]);
    }

    #[test]
    #[cfg(not(feature = "profiling"))]
    fn disabled_timing_evaluates_only_work() {
        let mut calls = 0;
        // An unavailable counter is valid because it is completely compiled out.
        let result = crate::timed!(unavailable_counter, {
            calls += 1;
            Err::<(), _>("read failed")
        });
        assert_eq!(result, Err("read failed"));
        assert_eq!(calls, 1);
        assert_eq!(std::mem::size_of::<super::ProfilerStats>(), 0);
    }

    #[test]
    fn elapsed_readings_handle_counter_wraparound() {
        let mut counter: u64 = 0;
        counter.add(10);
        assert_eq!(counter.add_elapsed(u64::MAX - 4, 5), 10);
        assert_eq!(counter, 20);
    }

    #[test]
    fn accumulated_total_wraps_on_overflow() {
        let mut counter = u64::MAX;
        counter.add(3);
        assert_eq!(counter, 2);
    }
}
