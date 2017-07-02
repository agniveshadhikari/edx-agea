"""
This module contains the methods that do the actual processing
on the excel files.
"""

from openpyxl import Workbook, load_workbook

def grade(questionPath, answerPath, solutionPath):
	"""
	Takes three file paths as arguments:
		The question file: contains the template and the marks
			for each cell in angled brackets
		The solution file: contains the correct solutions for each
			cell. Other cells are ignored
		The answer file: contains the actual file to be graded.
			Ungraded cells are ignored.

	Reuturns: The score received for the answer file
	"""
    annotated = Workbook()
    sample = Workbook()
    answer = Workbook()
    annotated = load_workbook(questionPath).active
    sample = load_workbook(solutionPath).active
    answer = load_workbook(answerPath).active

    score = 0

    for row in annotated.iter_rows():
        for cell in row:
            coord = cell.coordinate
            if str(annotated[coord].value)[0] == '<':
                if answer[coord].value == sample[coord].value:
                    score += int((annotated[coord].value)[1:-1])

    return score
    
def total_marks(questionPath):
	"""
	Takes the file path of the question file as argument
	Returns the maximum achievable score
	"""
    question = Workbook()
    question = load_workbook(questionPath).active
    score = 0
    for row in question.iter_rows():
        for cell in row:
            coord = cell.coordinate
            if str(question[coord].value)[0] == '<':
                score += int((question[coord].value)[1:-1])

    return score

