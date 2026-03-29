from collections import Counter

from gacha_pull_utils import validate_rates, simulate_one_run_counts


def run_meets_goal(run_counts, target_goal):
    """
    Return True if the run meets the requested goal.

    target_goal format:
      {rank: minimum_count_needed}

    Example:
      {8: 1, 7: 2}
    means the run succeeds only if it gets:
      - at least 1 rank-8
      - at least 2 rank-7
    """
    for rank, needed in target_goal.items():
        if run_counts[rank] < needed:
            return False
    return True


def simulate_many_runs_expectation(
    pulls_per_run,
    iterations,
    rates,
    guarantee_rank,
    guarantees_per_pull=1,
    bits_per_pull=11,
    target_goal=None,
    exclude_ranks=None,
):
    """
    Simulate many full runs and report two things:
    1) the average count of each rank per run
    2) the average total of all non-excluded ranks per run
    3) the chance of meeting a target goal, if one is provided

    This version has NO pity and NO prior-progress state.
    Every simulated run starts fresh.
    """
    validate_rates(rates)

    if pulls_per_run < 0:
        raise ValueError("pulls_per_run cannot be negative")
    if iterations <= 0:
        raise ValueError("iterations must be positive")

    target_goal = dict(target_goal or {})
    exclude_ranks = set(exclude_ranks or {0})

    print(f"Validity checks passed, running {iterations} iterations...")

    total_counts = Counter()
    goal_successes = 0

    for _ in range(iterations):
        run_counts = simulate_one_run_counts(
            rates=rates,
            guarantee_rank=guarantee_rank,
            guarantees_per_pull=guarantees_per_pull,
            bits_per_pull=bits_per_pull,
            pulls_per_run=pulls_per_run,
        )
        total_counts.update(run_counts)

        if target_goal and run_meets_goal(run_counts, target_goal):
            goal_successes += 1

    average_counts_per_run = {}
    for rank in sorted(rates.keys(), reverse=True):
        if rank in exclude_ranks:
            continue
        average_counts_per_run[rank] = total_counts[rank] / iterations

    average_non_excluded_total_per_run = sum(average_counts_per_run.values())

    print(
        f"Simulation: {iterations} runs, pulls_per_run={pulls_per_run}, "
        f"bits_per_pull={bits_per_pull}, guarantees_per_pull={guarantees_per_pull}, "
        f"guarantee_rank={guarantee_rank}"
    )
    print("Average count per run:")
    for rank in sorted(average_counts_per_run.keys(), reverse=True):
        print(f"  Rank {rank}: {average_counts_per_run[rank]:.4f}")
    print(f"Average total of non-excluded ranks per run: {average_non_excluded_total_per_run:.4f}")

    if target_goal:
        success_rate = (goal_successes / iterations) * 100
        print("Goal checked:")
        for rank in sorted(target_goal.keys(), reverse=True):
            print(f"  Rank {rank}: at least {target_goal[rank]}")
        print(f"Chance to meet goal: {success_rate:.2f}%")
    else:
        success_rate = None

    return {
        "average_counts_per_run": average_counts_per_run,
        "average_non_excluded_total_per_run": average_non_excluded_total_per_run,
        "goal_success_rate": success_rate,
    }


# ============================================================
# USER-EDITABLE SECTION
# ============================================================
# Change the values below to match the banner or ticket event you want to test.
#
# IMPORTANT TERMS:
# - bit  = one item/result inside a pull
# - pull = one full currency spend / ticket use / event draw
# - run  = the full set of pulls you want to simulate
#
# This simulator is for questions like:
# - "On average, how many rank-8 / rank-7 / rank-6 items do I get in this event?"
# - "What is my chance to get at least 2 rank-8s in 33 pulls?"
#
# This version has:
# - NO pity system
# - NO previous-pull tracking
# - support for multiple guarantees like 10 2G6 or 11 1G6
# ============================================================


# ------------------------------------------------------------
# BANNER ODDS
# ------------------------------------------------------------
# Put the chance for EACH possible bit result here.
#
# Format:
#   rank: chance_per_bit
#
# Notes:
# - These chances must add up to exactly 1.0
# - Usually rank 0 is true trash / junk
# - The simulator checks this automatically and will stop if the total is wrong
#
# Example below:
# - rank 8 = 2.5%
# - rank 7 = 3.5%
# - rank 6 = 4.04%
# - rank 5 = 4%
# - rank 0 = everything else
rates = {
    8: 0.025,
    7: 0.035,
    6: 0.0404,
    5: 0.0400,
    0: 1 - 0.1404,
}


# ------------------------------------------------------------
# PULL FORMAT
# ------------------------------------------------------------
# pulls_per_run
#   How many total pulls are in the full run you want to simulate.
#
#   Examples:
#   - 33 for a "33-pull" banner/event
#   - 14 for a 14-pull ticket event
#   - 10 for a 10-pull ticket batch
#
# bits_per_pull
#   How many bits/results are inside each pull.
#
#   Examples:
#   - 11 for an 11x relic draw
#   - 10 for a 10x ticket draw
#
# guarantee_rank
#   The minimum rank that counts toward the guarantee.
#
#   Examples:
#   - 1G6 means guarantee_rank = 6, guarantees_per_pull = 1
#   - 2G6 means guarantee_rank = 6, guarantees_per_pull = 2
#   - 3G8 means guarantee_rank = 8, guarantees_per_pull = 3
#
# guarantees_per_pull
#   How many guaranteed rank-or-better bits each pull must contain.
#
#   Examples:
#   - 11 1G6 => bits_per_pull=11, guarantees_per_pull=1, guarantee_rank=6
#   - 10 2G6 => bits_per_pull=10, guarantees_per_pull=2, guarantee_rank=6
#   - 33 3G8 is usually interpreted here as 33 pulls, each with 3 guaranteed 8+ bits
#
# IMPORTANT:
# The guarantees trigger as late as needed to make the pull legal.
# Example for 10 2G6:
# - if the first 8 bits contain no 6+, the 9th bit is forced to 6+
# - if the first 9 bits still contain fewer than 2 total 6+, the 10th bit is forced to 6+
pulls_per_run = 14
bits_per_pull = 10
guarantee_rank = 6
guarantees_per_pull = 1


# ------------------------------------------------------------
# GOAL CHECK (OPTIONAL)
# ------------------------------------------------------------
# Use this if you ALSO want the simulator to report the chance of meeting a goal.
#
# Format:
#   target_goal = {rank: minimum_count_needed}
#
# Examples:
#   {8: 1}
#     = chance to get at least one rank-8 in the full run
#
#   {8: 2, 7: 1}
#     = chance to get at least two rank-8s AND at least one rank-7
#
# If you only care about average results and do NOT want a goal check, use:
#   target_goal = {}
target_goal = {8: 1}


# ------------------------------------------------------------
# OUTPUT SETTINGS
# ------------------------------------------------------------
# iterations
#   Number of simulated runs.
#   More iterations = more accurate, but slower.
#
#   Good defaults:
#   - 10,000   = quick estimate
#   - 100,000  = good accuracy
#   - 500,000+ = very stable, but slower
#
# exclude_ranks
#   Ranks you do NOT want printed in the average-count results.
#   Most of the time, keep this as {0} to hide true trash.
#
# The simulator will also print:
#   Average total of non-excluded ranks per run
# which is the combined average of every rank that is NOT excluded here.
# Example: if exclude_ranks = {0}, this is the average total of 8+7+6+5 per run.
iterations = 100000
exclude_ranks = {0}


simulate_many_runs_expectation(
    pulls_per_run=pulls_per_run,
    iterations=iterations,
    rates=rates,
    guarantee_rank=guarantee_rank,
    guarantees_per_pull=guarantees_per_pull,
    bits_per_pull=bits_per_pull,
    target_goal=target_goal,
    exclude_ranks=exclude_ranks,
)
