from pymeasure.experiment import Worker

class PhDStudent(Worker):
    def __init__(self, name: str):
        super().__init__(name)
        