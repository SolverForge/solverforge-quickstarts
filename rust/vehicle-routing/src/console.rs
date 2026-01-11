//! Colorful console output.

use owo_colors::OwoColorize;

/// ASCII art banner for solver startup.
pub fn print_banner() {
    let banner = r#"
  ____        _                _____
 / ___|  ___ | |_   _____ _ __|  ___|__  _ __ __ _  ___
 \___ \ / _ \| \ \ / / _ \ '__| |_ / _ \| '__/ _` |/ _ \
  ___) | (_) | |\ V /  __/ |  |  _| (_) | | | (_| |  __/
 |____/ \___/|_| \_/ \___|_|  |_|  \___/|_|  \__, |\___|
                                             |___/
"#;
    println!("{}", banner.cyan().bold());
    println!(
        "  {} {}\n",
        format!("v{}", env!("CARGO_PKG_VERSION")).bright_black(),
        "Vehicle Routing".bright_cyan()
    );
}
