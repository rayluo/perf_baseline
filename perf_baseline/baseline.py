import inspect
import json
import logging
import time
from timeit import Timer


__version__ = "0.1.0"
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def timeit(stmt, setup=None, globals=None, name=None):
    """Return the seconds needed to run the statement, after many sampling.

    Parameters ``setup`` and ``globals`` are the same as
    `Python's timeit <https://docs.python.org/3/library/timeit.html?highlight=timeit#timeit.timeit>`_.
    Parameter ``name`` is only used for readability in logs.

    Internally, this function will determine the right number to repeat,
    so that the test will always finish in roughly 2 to 5 seconds
    (unless a single run of your ``stmt`` is already slower than that).
    """
    timer = Timer(
        stmt=stmt,  # f.run would be 2x faster than stmt="f.run()" & setup="f=Foo()"
        setup=setup or "pass",
        globals=globals,  # globals is unnecessary when timing a class method
        )
    runs, elapsed = timer.autorange()  # number of runs that took 0.2+ second
    logger.debug("%s: sampling: %f seconds", name or stmt, elapsed)
    number = runs  # The proper number to reduce func call overhead for fast stmt
    repeat = 10  # Repeat multiple times to approach minimum
    begin = time.time()
    t = min(timer.repeat(  # Use min() based on suggestion from official docs
        # https://docs.python.org/3/library/timeit.html#timeit.Timer.repeat
        repeat=repeat, number=number))
    logger.debug("%s: timeit() took %f seconds", name or stmt, time.time() - begin)
    logger.info(
        "%s: %f sec/op = %f ops/sec (%dx%d runs sampled)",
        name or stmt, t/number, number/t, number, repeat)
    return t/number


class RegressionError(RuntimeError):
    pass


class Baseline(object):
    """Stores initial performance baseline(s) and compares it with subsequent runs.

    Once an initial baseline is set in stone, it will never change.
    You will then compare future runs against the same initial baseline,
    rather than comparing against an ever-shifting last commit.
    This way, your performance regression detection is unsusceptible to
    gradual performance decline.
    """

    def __init__(self, filename, threshold=None):
        """Define a baseline object whose data will be stored in ``filename``.

        Performance is measured by a ratio of new duration divided by baseline.
        For example, 1.5 means the new performance is 50% slower than baseline,
        and 0.5 means the new performance is 2x faster than baseline.

        The ``threshold`` is defined as the upper bound of the performance ratio.
        Slower than threshold will trigger a ``RegressionError`` exception.

        Note that baseline is only meaningful when it was run on the same machine.
        If you are benchmarking your code on a new machine,
        you do NOT want to copy the old baselines from your old machine.

        To recalibrate on the same machine, simply delete the file and then rerun.
        """
        self._filename = filename  # Accepting a fileobj would be error-prone because caller might not open it with mode "r+"
        logger.info("Baseline file: %s", filename)
        self._threshold = threshold or 1.5

    def _setdefault(self, name, elapsed):
        try:
            with open(self._filename) as f:
                baseline = json.load(f)
        except FileNotFoundError:
            baseline = {}
        if name not in baseline:
            baseline[name] = {
                "elapsed": elapsed,
                "created_at": time.ctime(),
            }
            with open(self._filename, "w") as f:
                json.dump(baseline, f, indent=2, sort_keys=True)
        else:
            data_point = baseline[name]["elapsed"]
            ratio = elapsed / data_point
            message = "{}: Actual/Baseline = {:.9f}/{:.9f} = {:.3} (VS threshold {:.2})".format(
                name, elapsed, data_point, ratio, self._threshold)
            logger.info(message)
            if ratio > self._threshold:
                raise RegressionError(message)

    def set_or_compare(self, stmt, name=None, setup=None, globals=None):
        """This method can be used to detect performance regression.

        It will do one of two things:

        1. Time the ``stmt`` and set it as an initial baseline (if there wasn't one)
        2. Subsequent runs will automatically compare against the initial baseline,
           and raise ``RegressionError`` when performance regression is detected.

        Each baseline object can contain many data points, differentiated by their names.
        ``name`` shall be a unique key in the current baseline.
        If ``name`` is ``None``, the caller's function name will be used instead.

        ``setup`` and ``globals`` will be relayed to underlying ``time.timeit()``.
        """
        name = inspect.currentframe().f_back.f_code.co_name if name is None else name
        self._setdefault(name, timeit(stmt, setup=setup, globals=globals, name=name))

