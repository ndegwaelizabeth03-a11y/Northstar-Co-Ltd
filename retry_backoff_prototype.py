"""
retry_backoff_prototype.py

Mini-prototype: retry with exponential backoff.

This is intentionally standalone -- no Flask, no dashboard, no cache,
no warehouse API. It isolates just the retry/backoff mechanism so it
demonstrates that one tool on its own, not the whole sync system it
originally lived inside.

Behavior:
    - call something that might fail
    - if it fails, wait, then try again
    - each retry waits longer than the last (exponential backoff):
          attempt 1 fails -> wait 1s
          attempt 2 fails -> wait 2s
          attempt 3 fails -> wait 4s
    - after MAX_RETRIES failures, give up gracefully instead of
      retrying forever
"""

import time


MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1


class SimulatedAPIError(Exception):
    """Stands in for a real network/API failure."""
    pass


def flaky_call(fail_times=2):
    """
    Simulates an unreliable API call. Fails `fail_times` times in a
    row, then succeeds on the next attempt.

    Change fail_times to see different outcomes:
      fail_times=2               -> succeeds on the 3rd attempt
      fail_times=MAX_RETRIES + 1 -> never succeeds, all retries exhausted
    """
    flaky_call.attempts += 1
    if flaky_call.attempts <= fail_times:
        raise SimulatedAPIError(f"simulated failure on attempt {flaky_call.attempts}")
    return {"status": "success", "attempt": flaky_call.attempts}


flaky_call.attempts = 0


def call_with_retry():
    """
    Calls flaky_call(), retrying up to MAX_RETRIES times with
    exponential backoff if it fails.
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = flaky_call()
            print(f"[success] {result}")
            return result

        except SimulatedAPIError as e:
            if attempt < MAX_RETRIES:
                backoff_seconds = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                print(f"[warning] {e}")
                print(f"[retry] attempt {attempt + 1}/{MAX_RETRIES} in {backoff_seconds}s...")
                time.sleep(backoff_seconds)
            else:
                print(f"[error] all {MAX_RETRIES} retries failed. Giving up.")
                return None


if __name__ == "__main__":
    call_with_retry()
