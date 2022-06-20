from math import ceil, floor
from random import random, uniform
import sys
import os
import re
from time import sleep

class Lexer:
	def __init__(self, text, rules, file):
		self.text = text
		self.rules = rules
		self.line = 1
		self.column = 1
		self.pos = 0
		self.comment = False
		self.file = file
	def next(self):
		t = self.text[self.pos:]
		if len(t) < 1:
			return None
		if t == '"':
			self.comment = not self.comment
		if self.comment:
			return None
		for r in self.rules:
			m = re.match(r, t)
			if m:
				command = m.group(0)
				self.pos += len(command)
				if '\n' in command:
					self.line += command.count('\n')
					self.column += len(command.rsplit('\n', 1)[-1])
				else:
					self.column += len(command)
				return (command, self.line, self.column, self.file)
		raise_error(("Syntax error at %d:%d in %s" % (self.line, self.column, self.file)), 1)

class Parser:
	def __init__(self, flags):
		self.flags = flags
		self.t = None
	def parse(self, lex:Lexer):
		self.t = lex.next()
		block = []
		while self.t and self.t[0] != "]" and self.t[0] != "@]" and self.t[0] != ")":
			block.append(self.parsecmd())
		return block
	def parsecmd(self, lex:Lexer):
		while '"' in self.t[0] or ":" in self.t[0] or self.t[0].isspace():
			self.t = lex.next()
			if not self.t:
				raise_error(("Syntax error at %d:%d in %s - expected a command" % (self.t[1], self.t[2], self.t[3])))
		if self.t[0] == "'" or self.t[0].startswith("|"):
			token = self.t
			out = (token, self.parsecmd(lex))
		elif self.t[0] == "[" or self.t[0] == "[@" or self.t[0] == "(":
			closetok = {"[":"]", "[@":"@]", "(":")"}[self.t[0]]
			token = self.t
			out = (token, self.parse(lex))
			if self.t != closetok:
				raise_error(("Syntax error at %d:%d in %s - expected '%s'" % (self.t[1], self.t[2], self.t[3])))
		else:
			out = token
		self.t = lex.next()
		return out

class Runner:
	def __init__(self, root_path, warner, flags):
		self.root_path = root_path
		self.valid_commands = [
			"'", # local-
			"\\|\\|", # repeat by value-
			"\\|\\-?[0-9]+\\|", # repeat by constant-
			"!", # increment
			"~", # decrement
			"\\+", # add
			"\\-", # subtract
			"\\*", # multiply
			"\\/", # divide
			"`", # generate a random number from 0 (inclusive) to 1 (exclusive)
			"\\>", # move right
			"\\<", # move left
			"\\_", # floor
			"\\&", # ceil
			"\\^", # switch active memory
			"\\[@", # do-while start
			"@\\]", # do-while end
			"\\[", # while start
			"\\]", # while end
			"\\{", # function ptr left
			"\\}", # function ptr right
			"\\(", # function def start
			"\\)", # function def end
			"%", # function call
			"\\$.", # input number
			"\\$\,", # input string
			"\\\\.", # output number
			"\\\\,", # output string
			"\\?\\?", # set the cell to its index
			"\\?\\=", # if the active memory cell = the not active memory cell, break
			"\\?\\<", # if the active memory cell < the not active memory cell, break
			"\\?\\>", # if the active memory cell > the not active memory cell, break
			";", # switch value of the active local memory cell and global memory cell
			":\r?\n", # end of line
			":$", # end of line with any character after
			"\"[^\"]*\"", # comments
			"[ \t\f\v]" # whitespace
		]
		self.opposite_commands = {
			"!": "~",
			"~": "!",
			"+": "-",
			"-": "+",
			"*": "/",
			"/": "*",
			">": "<",
			"<": ">",
			"{": "}"
		}
		self.memory = [[0.0], [0.0]]
		self.pointers_mem = [0, 0]
		self.functions = [None]
		self.pointer_func = 0
		self.program = []
		self.programstack = []
		self.mem_stack = []
		self.pointers_mem_stack = []
		self.warner = warner
		self.flags = flags

	def run_file(self, file_path):
		file = open(os.path.join(self.root_path, file_path), "r")
		program = file.read()
		file.close()
		self.run(program, file_path)

	def run_user_input(self, program):
		self.run(program, "<input_main>")

	def run(self, program, file):
		lexer = Lexer(program, self.valid_commands, file)
		parser = Parser(self.flags)
		self.program = parser.parse(lexer)
		if "--debug" in self.flags:
			print("Program:")
			print(repr(program))
			print("Commands:")
			print(repr(self.program))
		self.run_call(self.program)
		if "--debug" in self.flags:
			print("\nMain memory:")
			print(self.memory)
			print("Local memory:")
			print(self.mem_stack)
	def run_call(self, block):
		self.mem_stack.append([[0.0],[0.0]])
		self.pointers_mem_stack.append([0, 0])
		self.run_block(block)
		self.mem_stack.pop()
		self.pointers_mem_stack.pop()
	def run_block(self, block):
		for cmd in block:
			if self.run_command(cmd):
				break
			if "--debug-heavy" in self.flags:
				print("Command:")
				print(cmd)
				print("Global memory:")
				print(self.memory)
				print("Global memory pointers:")
				print(self.pointers_mem)
				print("Active global memory:")
				sleep(0.5)
	def run_command(self, command, local=False, repeat=1):
		cmdi = command if command[0] is str else command[0]
		cmdstr = cmdi[0]
		if cmdstr == "'":
			self.run_command(command[1], True, repeat)
		elif cmdstr == "||":
			self.run_command(command[1], False, repeat * self.get_cell(local)) # False here is intentional
		elif cmdstr.startswith("|"):
			self.run_command(command[1], False, repeat * int(cmdstr[1:-1])) # False here is intentional
		elif cmdstr == "[@":
			if repeat != 1:
				raise_error(("Runtime error at %d:%d in %s - can't repeat loops" % (cmdi[1], cmdi[2], cmdi[3])))
			self.run_block(command[1])
			while self.get_cell(local) != 0:
				self.run_block(command[1])
		elif cmdstr == "[":
			if repeat != 1:
				raise_error(("Runtime error at %d:%d in %s - can't repeat loops" % (cmdi[1], cmdi[2], cmdi[3])))
			while self.get_cell(local) != 0:
				self.run_block(command[1])
		elif cmdstr == "(":
			if repeat != 1:
				raise_error(("Runtime error at %d:%d in %s - can't repeat function definition" % (cmdi[1], cmdi[2], cmdi[3])))
			self.functions[self.pointer_func] = command[1]
		else:
			return self.run_basic_command(cmdstr, cmdi, local, repeat)
		return False
	def run_basic_command(self, command, commandinfo, local=False, repeat=1):
		if command == "!":
			self.set_cell(self.get_cell(local) + repeat, local)
		elif command == "~":
			self.set_cell(self.get_cell(local) - repeat, local)
		elif command == "+":
			self.set_cell(self.get_cell(local) + self.get_cell(local, False) * repeat, local)
		elif command == "-":
			self.set_cell(self.get_cell(local) - self.get_cell(local, False) * repeat, local)
		elif command == "*":
			self.set_cell(self.get_cell(local) * self.get_cell(local, False) * repeat, local)
		elif command == "/":
			self.set_cell(self.get_cell(local) / self.get_cell(local, False) * repeat, local)
		elif command == "`":
			self.set_cell(uniform(0, 1), local)
		elif command == ">":
			if local:
				mem = self.mem_stack[-1]
				ptrs = self.pointers_mem_stack[-1]
			else:
				mem = self.memory
				ptrs = self.pointers_mem
			ptrs[0] += repeat
			while ptrs[0] < 0:
				ptrs[0] += 1
				mem[0].insert(0, 0.0)
			while ptrs[0] > len(mem[0]):
				mem[0].append(0.0)
		elif command == "<":
			if local:
				mem = self.mem_stack[-1]
				ptrs = self.pointers_mem_stack[-1]
			else:
				mem = self.memory
				ptrs = self.pointers_mem
			ptrs[0] -= repeat
			while ptrs[0] < 0:
				ptrs[0] += 1
				mem[0].insert(0, 0.0)
			while ptrs[0] > len(mem[0]):
				mem[0].append(0.0)
		elif command == "_":
			self.set_cell(floor(self.get_cell(local)), local)
		elif command == "&":
			self.set_cell(ceil(self.get_cell(local)), local)
		elif command == "^":
			if repeat % 2 == 0:
				return False
			if local:
				self.mem_stack[-1][0], self.mem_stack[-1][1] = self.mem_stack[-1][1], self.mem_stack[-1][0]
				self.pointers_mem_stack[-1][0], self.pointers_mem_stack[-1][1] = self.pointers_mem_stack[-1][1], self.pointers_mem_stack[-1][0]
			else:
				self.memory[0], self.memory[1] = self.memory[1], self.memory[0]
				self.pointers_mem[0], self.pointers_mem[1] = self.pointers_mem[1], self.pointers_mem[0]
		elif command == "{":
			self.pointer_func -= repeat
			while self.pointer_func < 0:
				self.pointer_func += 1
				self.functions.insert(0, None)
			while self.pointer_func > len(self.functions):
				self.functions.append(None)
		elif command == "}":
			self.pointer_func += repeat
			while self.pointer_func < 0:
				self.pointer_func += 1
				self.functions.insert(0, None)
			while self.pointer_func > len(self.functions):
				self.functions.append(None)
		elif command == "%":
			if repeat < 0:
				raise_error(("Runtime error at %d:%d in %s - can't repeat function calls negative number of times" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			f = self.functions[self.pointer_func]
			for _ in range(repeat):
				self.run_call(f)
		elif command == "$.":
			if repeat != 1:
				raise_error(("Runtime error at %d:%d in %s - can't repeat number input" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			self.set_cell(float(input()), local)
		elif command == "$,":
			if repeat != 1:
				raise_error(("Runtime error at %d:%d in %s - can't repeat character input" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			self.set_cell(ord(sys.stdin.read(1)), local)
		elif command == "\.":
			if repeat < 0:
				raise_error(("Runtime error at %d:%d in %s - can't repeat number output negative number of times" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			print(str(self.get_cell(local)) * repeat, end="")
		elif command == "\,":
			if repeat < 0:
				raise_error(("Runtime error at %d:%d in %s - can't repeat character output negative number of times" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			print(chr(int(self.get_cell(local))) * repeat, end="")
		elif command == "??":
			if repeat != 1:
				raise_error(("Runtime error at %d:%d in %s - can't repeat 'set to index'" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			self.set_cell(self.pointers_mem_stack[-1][0] if local else self.pointers_mem[0], local)
		elif command == "?>":
			if repeat != 1:
				raise_error(("Runtime error at %d:%d in %s - can't repeat conditional breaks" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			if self.get_cell(local) > self.get_cell(local, False):
				return True
		elif command == "?=":
			if repeat != 1:
				raise_error(("Runtime error at %d:%d in %s - can't repeat conditional breaks" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			if self.get_cell(local) == self.get_cell(local, False):
				return True
		elif command == "?<":
			if repeat != 1:
				raise_error(("Runtime error at %d:%d in %s - can't repeat conditional breaks" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			if self.get_cell(local) < self.get_cell(local, False):
				return True
		elif command == ";":
			if repeat % 2 == 0:
				return False
			if local:
				raise_error(("Runtime error at %d:%d in %s - local-global value switch can't be local" % (commandinfo[1], commandinfo[2], commandinfo[3])))
			tmp = self.get_cell()
			self.set_cell(self.get_cell(True))
			self.set_cell(tmp, True)
		return False

	def get_cell(self, local=False, active=True):
		active_id = 0 if active else 1
		if local:
			return self.mem_stack[-1][active_id][self.pointers_mem_stack[active_id]]
		else:
			return self.memory[active_id][self.pointers_mem[active_id]]
	def set_cell(self, value, local=False, active=True):
		active_id = 0 if active else 1
		if local:
			self.mem_stack[-1][active_id][self.pointers_mem_stack[active_id]] = value
		else:
			self.memory[active_id][self.pointers_mem[active_id]] = value


class Warner:
	def __init__(self, flags):
		self.disabled = []
		for flag in flags:
			flag = flag.lower()
			if flag == "--disable-warnings":
				self.disabled.append("all")
			elif flag == "--disable-path-warning":
				self.disabled.append("path")
			elif flag == "--disable-too-left-pointer-warning":
				self.disabled.append("too-left-pointer")

	def warn(self, warning_type):
		if "all" in self.disabled or warning_type in self.disabled:
			return
		if warning_type == "path":
			print("Warning: No code path supplied, this will make it impossible to run files from the code (you can use the --disable-warnings flag to disable all warnings or --disable-path-warning to disable this particular warning)")
			return
		if warning_type == "too-left-pointer":
			print("You moved to the -1 index in memory. This will not crash the program, but should generally be avoided (you can use the --disable-warnings flag to disable all warnings or --disable-too-left-pointer-warning to disable this particular warning)")

def raise_error(text, code = 1):
		print(text)
		sys.exit(code)

if __name__ == "__main__":
	args = sys.argv
	debug_heavy = False
	flags = []
	possible_flags = [
		"--debug",
		"--debug-heavy",
		"-",
		"--disable-warnings",
		"--disable-path-warning",
		"--disable-too-left-pointer-warning"
	]
	args_amount = len(args)
	path = None
	program = None
	for i in range(0, args_amount):
		arg = args[i]
		if arg == "-" and not "-" in flags and i < args_amount - 1:
			program = args[i+1]
			flags.append("-")
			continue
		if arg == "--debug-heavy" and not "--debug" in flags:
			flags.append("--debug")
		if arg in possible_flags and not arg in flags:
			flags.append(arg)
	if not "-" in flags:
		path: str = input("Input the complete path to your maumivu.au file: ") if args_amount < 2 else args[1]
		if path.endswith("maumivu.au"):
			path = path[0:-10]

	warner = Warner(flags)
	if path == None:
		warner.warn("path")

	runner = Runner(path, warner, flags)
	if program == None:
		runner.run_file("maumivu.au")
	else:
		runner.run_user_input(program)
