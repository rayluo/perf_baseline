# Run this file by "pytest --log-cli-level INFO" to read benchmark information
import os, time
import pytest
from perf_baseline import timeit, Baseline, RegressionError


def add(a, b):
    return a + b


def test_time_a_function_with_parameter():
    elapsed = timeit(
        "add(2, 3)",  # Use string notation to time a function with parameter(s)
        globals={"add": add},  # And provide the function definition by globals
    )
    assert elapsed > 0, "timeit() shall return the time needed to run your function"


class Demo(object):
    """Organize your test case as a class if it requires expensive initialization.
    """
    def __init__(self, a, b):
        time.sleep(3)  # Mimic an expensive initialization
        self._a = a
        self._b = b

    def run(self):
        """If your test function needs no parameter, it will be easier to test"""
        time.sleep(0.000001)  # This is a regression comparing to the add() implementation
        return self._a + self._b


def test_time_a_callable_without_parameter():
    d = Demo(2, 3)  # This line may take long time
    elapsed = timeit(d.run)  # Accepts a callable, as long as it requires no parameter
    assert elapsed > 0, "timeit() shall return the time needed to run your function"


def test_baseline():
    filename = ".test.baseline"
    try:
        os.unlink(filename)
    except FileNotFoundError:
        pass
    baseline = Baseline(filename, threshold=2.0)  # We will detect 2x slow regression
    baseline.set_or_compare("add(2, 3)", name="our test subject", globals={"add": add})
    with open(filename) as f:
        snapshot1 = f.read()
    baseline.set_or_compare("add(4, 5)", name="our test subject", globals={"add": add})
    with open(filename) as f:
        snapshot2 = f.read()
    assert snapshot1 == snapshot2, "The first run should be set in stone as baseline"
    with pytest.raises(RegressionError):
        # Now we will test a different implementation which happens to run slower
        demo = Demo(2, 3)
        baseline.set_or_compare(demo.run, name="our test subject")
    os.unlink(filename)

