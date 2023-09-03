# Perf Baseline

The ``perf_baseline`` is a performance regression detection tool for Python projects.
It uses ``timeit`` to automatically time your function,
records the result as a baseline into a file,
and compares subsequent test results against the initial baseline
to detect performance regression based on your specified threshold.
(We do not compare against the second-last performance test result,
therefore your performance won't suffer from gradual decline.)


## Installation

`pip install perf_baseline`

## Usage 1: Benchmark functions with parameters

Let's say your project contains some important functions like this:

```python
def add(a, b):
    return a + b

def sub(a, b):
    return a - b
```

You can guard against potential performance regression by:

```python
from perf_baseline import Baseline

baseline = Baseline(
    "my_baseline.bin",  # Performance test result will be saved into this file
    threshold=1.8,  # Subsequent tests will raise exception if a new test is more than 1.8x slower than the baseline
)

def test_add_should_not_have_regression():
    baseline.set_or_compare("add(2, 3)", name="my addition implementation", globals={"add": add})

def test_sub_should_not_have_regression():
    baseline.set_or_compare("sub(5, 4)", globals={"sub": sub})
    # Note: When absent, name defaults to the current test function's name,
    #       which is "test_sub_should_not_have_regression" in this case
```

That is it.

Now you can run ``pytest`` to test it, or ``pytest --log-cli-level INFO`` to see some logs.
The test case will pass if there is no performance regression, or raise ``RegressionError`` otherwise.

Under the hood, ``perf_baseline`` stores the *initial* test results into the file you specified.
Each file may contain multiple data points, differentiated by their unique names.
If the ``name`` parameter is omitted, the current test case's name will be used instead.

Subsequent tests will automatically be compared with the initial baseline,
and error out when performance regression is detected.

If you want to reset the baseline, simply delete that baseline file and then start afresh.


## Usage 2: Test a parameter-less callable

In real world projects, your test subject may require nontrivial setup,
such as prepopulating some test data,
and those initialization time shall be excluded from benchmark.
How do we achieve that?

A common solution is creating a wrapper class,
which has an expensive constructor and a (typically parameter-less) action method.
And then you can have ``Baseline`` to check that action method.
For example:

```python
class TestDriver:
    def __init__(self, size):
        self.data = list(range(size))
        import random
        random.shuffle(self.data)
    def run(self):
        self.data.sort()  # Some implementation to sort the self.data in-place

baseline = Baseline("my_baseline.bin", threshold=2.0)

def test_my_sort_implementation():
    driver = TestDriver(1000*1000)
    baseline.set_or_compare(
        driver.run,  # A parameter-less callable can be tested as-is, without setting globals
    )

    # Alternatively, you may also combine the above two lines into this one-liner
    baseline.set_or_compare(TestDriver(1000*1000).run)  # The driver initialization is still done only once
```


## Do NOT commit the baseline file into Git

Add your baseline filename into your ``.gitignore``, so that you won't accidentally commit it.

```
my_baseline.bin
```

Why?

The idea is that a performance baseline (such as 123456 ops/sec) is
only meaningful and consistent when running on the *same* computer.
Switching to a different computer, it will have a different baseline.

By not committing a baseline into the source code repo,
each maintainer of your project (and each of their computers)
will have their own baseline created by the first run.

This way, you won't need to use a large threshold across different computers
(it is impossible to specify a constant threshold that works on different computers anyway).
Per-computer baselines all self-calibrate to match the performance of each computer.


## How to run this in Github Action?

``perf_baseline`` relies on an *updatable* baseline file,
which shall be writable when a new data point (represented by a new ``name``) occurs,
and remain read-only when an old data point (represented by same ``name``) already exists.

As of this writing, [Github's Cache Action](https://github.com/marketplace/actions/cache)
supports the updatable usage via some hack, inspired by
[this hint](https://github.com/actions/toolkit/issues/505#issuecomment-1650290249).
Use the following snippet, and modify its ``path`` and ``hashFiles(...)`` to match your filenames.

```yaml
    - name: Setup an updatable cache for Performance Baselines
      uses: actions/cache@v3
      with:
        path: my_baseline.bin
        key: ${{ runner.os }}-performance-${{ hashFiles('tests/test_benchmark.py') }}
        restore-keys: ${{ runner.os }}-performance-
    - name: Now you can run test cases powered by perf_baseline
      ...
```


## How to choose an appropriate threshold?

The performance of an implementation always fluctuates a little.
You need an appropriate threshold to detect performance regression.
An excessive threshold will not catch a performance regression.
An inadequate threshold will yield many false positives.
You shall run some preliminary tests to see the normal range of fluctuation.

1. Start with a bigger threshold, such as 10 (which means tolerating 10x slower runs).
2. Run your ``perf-baseline``-powered test cases multiple times,
   with logs enabled (i.e. ``pytest --log-cli-level INFO``),
   and focus on the lines with ``Actual/Baseline = ..../.... = 1.234 (VS threshold 10)``,
   take notes on that ratio number (1.234 in the example above).
3. After you have a bunch of ratio samples, uses the highest/lowest plus a sensible margin as the threshold.

<!--
TODO: Shall perf_baseline automate this process in next version, so that the users do not have to?
A threshold can probably be detected in one run, by examining its stdev.
Note that a threshold auto-detected on one machine may not be suitable for another,
so, human decision is probably still necessary to choose a bigger threshold to sustain fluctuation.
-->

FYI, benchmarks running on bare metal are usually consistent within 10% to 20% (i.e. threshold=1.2).
The agents/runners of Github Actions seem to fluctuate a lot, possibly caused by
["noisy neighbor" effect](https://en.wikipedia.org/wiki/Cloud_computing_issues#Performance_interference_and_noisy_neighbors).

