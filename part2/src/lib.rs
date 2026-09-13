mod profiler;
mod timer;

pub use profiler::{ProfilerStats, TickCounter};
pub use timer::{estimate_timer_frequency_hz, read_ticks, timer_frequency_hz, timer_name};
