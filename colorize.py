
BLACK   = 0
RED     = 1
GREEN   = 2
YELLOW  = 3
BLUE    = 4
MAGENTA = 5
CYAN    = 6
WHITE   = 7

TOKEN = '\033['

def c(text, color=None, bright=False, dark=False):
	return '' \
		+ TOKEN \
		+ ('' if dark else ';') \
		+ ('' if color == None else str(30 + color)) \
		+ (';1' if bright else '') \
		+ 'm' \
		+ text \
		+ TOKEN \
		+ ('' if dark else '0') \
		+ 'm'

def u(text):
	if text.startswith(TOKEN):
		m = text.find('m')
		end = text.rfind(TOKEN)
		return text[m+1:end]
	return text
