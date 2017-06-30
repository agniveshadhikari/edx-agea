from openpyxl import *
import logging

log = logging.getLogger(__name__)



def grade(questionPath, answerPath, solutionPath):
    annotated = Workbook()
    sample = Workbook()
    answer = Workbook()
    log.info(questionPath)
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

