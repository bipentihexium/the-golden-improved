use regex::Regex;

pub struct Validator {}

impl Validator {
	pub fn run(mut lexer: super::Lexer) -> Result<u8, String> {
		let mut t = lexer.next();
		let mut p = t.clone();
		while t.is_ok() && t.clone().unwrap().is_some() {
			p = t;
			t = lexer.next();
		}
		match t {
			Err(e) => return Err(e),
			_ => {}
		}
		let (command, line, column, file_path) = p.unwrap().unwrap();
		if !Regex::new(r":\n?\r?").unwrap().is_match(&command) {
			return Err(format!("Syntax error at {}:{} in {:?} ({:?}) - ':' expected", line, column, file_path.file_name().unwrap(), file_path.as_path()));
		}
		return Ok(0);
	}
}