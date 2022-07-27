use dotenv::dotenv;
use std::env;

#[path = "./flags.rs"] mod flags;
pub use flags::Flags;
#[path = "./interpreter/interpreter.rs"] mod interpreter;
use interpreter::Interpreter;

fn main() {
	dotenv().ok();
	if env::var("RUST_LOG").is_err() {
		env::set_var("RUST_LOG", "INFO");
	}
	match env::var("LOGS") {
		Ok(val) => {
			if val.to_lowercase() != "on" && cfg!(target_os = "windows") {
				winconsole::window::hide();
			}
		}
		Err(_) => {
			if cfg!(target_os = "windows") {
				winconsole::window::hide();
			}
		}
	}
	tracing_subscriber::fmt::init();

	let args: Vec<String> = std::env::args().collect();

	let mut flags_handler = Flags::new();
	flags_handler.parse(&args);

	let mut action = String::new();
	let mut version = String::from("latest");
	let mut code = String::new();
	let mut code_path = std::path::PathBuf::new();

	let cloned_flags = flags_handler.clone();
	if let Some(a) = cloned_flags.action {
		action = a;
	}
	if let Some(path) = cloned_flags.code_path {
		code = match std::fs::read_to_string(&path) {
			Ok(c) => c,
			Err(e) => panic!("{}", e)
		};
		code_path = path;
	} else if let Some(code_to_run) = cloned_flags.raw_code_to_run {
		code = code_to_run;
		code_path.set_file_name("<console_input_main>");
	}
	if let Some(v) = cloned_flags.version {
		version = v;
	}
	if action == *"run" {
		Interpreter::new(version, code, code_path, flags_handler).run();
	} else {
		todo!()
	}
}
