"""
Constraint tests for the employee scheduling quickstart.

Each constraint is tested with both penalizing and non-penalizing scenarios.
"""
from solverforge_legacy.solver.test import ConstraintVerifier

from employee_scheduling.domain import Employee, Shift, EmployeeSchedule
from employee_scheduling.constraints import (
    define_constraints,
    required_skill,
    no_overlapping_shifts,
    at_least_10_hours_between_two_shifts,
    one_shift_per_day,
    unavailable_employee,
    undesired_day_for_employee,
    desired_day_for_employee,
    balance_employee_shift_assignments,
)

from datetime import date, datetime, time, timedelta
import pytest

# Test constants
DAY_1 = date(2021, 2, 1)
DAY_2 = date(2021, 2, 2)
DAY_3 = date(2021, 2, 3)
DAY_START_TIME = datetime.combine(DAY_1, time(9, 0))
DAY_END_TIME = datetime.combine(DAY_1, time(17, 0))
AFTERNOON_START_TIME = datetime.combine(DAY_1, time(13, 0))
AFTERNOON_END_TIME = datetime.combine(DAY_1, time(21, 0))

constraint_verifier = ConstraintVerifier.build(
    define_constraints, EmployeeSchedule, Shift
)


# ========================================
# Required Skill Tests
# ========================================

class TestRequiredSkill:
    """Tests for the required_skill constraint."""

    def test_penalized_when_employee_lacks_skill(self):
        """Employee without required skill should be penalized."""
        employee = Employee(name="Amy")  # No skills
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Driving",
            employee=employee,
        )
        constraint_verifier.verify_that(required_skill).given(
            employee, shift
        ).penalizes(1)

    def test_not_penalized_when_employee_has_skill(self):
        """Employee with required skill should not be penalized."""
        employee = Employee(name="Amy", skills={"Driving"})
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Driving",
            employee=employee,
        )
        constraint_verifier.verify_that(required_skill).given(
            employee, shift
        ).penalizes(0)

    def test_not_penalized_when_employee_has_multiple_skills(self):
        """Employee with multiple skills including required should not be penalized."""
        employee = Employee(name="Amy", skills={"Driving", "First Aid", "Cooking"})
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="First Aid",
            employee=employee,
        )
        constraint_verifier.verify_that(required_skill).given(
            employee, shift
        ).penalizes(0)

    def test_penalized_when_employee_has_different_skills(self):
        """Employee with skills but not the required one should be penalized."""
        employee = Employee(name="Amy", skills={"Cooking", "Cleaning"})
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Driving",
            employee=employee,
        )
        constraint_verifier.verify_that(required_skill).given(
            employee, shift
        ).penalizes(1)


# ========================================
# Overlapping Shifts Tests
# ========================================

class TestNoOverlappingShifts:
    """Tests for the no_overlapping_shifts constraint."""

    def test_penalized_when_shifts_fully_overlap(self):
        """Same employee with fully overlapping shifts should be penalized."""
        employee = Employee(name="Amy")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location A",
            required_skill="Skill",
            employee=employee,
        )
        shift2 = Shift(
            id="2",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location B",
            required_skill="Skill",
            employee=employee,
        )
        # 8 hours overlap = 480 minutes
        constraint_verifier.verify_that(no_overlapping_shifts).given(
            employee, shift1, shift2
        ).penalizes_by(480)

    def test_penalized_when_shifts_partially_overlap(self):
        """Same employee with partially overlapping shifts should be penalized by overlap duration."""
        employee = Employee(name="Amy")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,  # 9:00
            end=DAY_END_TIME,      # 17:00
            location="Location A",
            required_skill="Skill",
            employee=employee,
        )
        shift2 = Shift(
            id="2",
            start=AFTERNOON_START_TIME,  # 13:00
            end=AFTERNOON_END_TIME,      # 21:00
            location="Location B",
            required_skill="Skill",
            employee=employee,
        )
        # Overlap from 13:00 to 17:00 = 4 hours = 240 minutes
        constraint_verifier.verify_that(no_overlapping_shifts).given(
            employee, shift1, shift2
        ).penalizes_by(240)

    def test_not_penalized_when_different_employees(self):
        """Different employees with overlapping shifts should not be penalized."""
        employee1 = Employee(name="Amy")
        employee2 = Employee(name="Beth")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location A",
            required_skill="Skill",
            employee=employee1,
        )
        shift2 = Shift(
            id="2",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location B",
            required_skill="Skill",
            employee=employee2,
        )
        constraint_verifier.verify_that(no_overlapping_shifts).given(
            employee1, employee2, shift1, shift2
        ).penalizes(0)

    def test_not_penalized_when_shifts_dont_overlap(self):
        """Same employee with non-overlapping shifts should not be penalized."""
        employee = Employee(name="Amy")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location A",
            required_skill="Skill",
            employee=employee,
        )
        shift2 = Shift(
            id="2",
            start=DAY_START_TIME + timedelta(days=1),
            end=DAY_END_TIME + timedelta(days=1),
            location="Location B",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(no_overlapping_shifts).given(
            employee, shift1, shift2
        ).penalizes(0)


# ========================================
# One Shift Per Day Tests
# ========================================

class TestOneShiftPerDay:
    """Tests for the one_shift_per_day constraint."""

    def test_penalized_when_two_shifts_same_day(self):
        """Employee with two shifts on same day should be penalized."""
        employee = Employee(name="Amy")
        shift1 = Shift(
            id="1",
            start=datetime.combine(DAY_1, time(6, 0)),
            end=datetime.combine(DAY_1, time(10, 0)),
            location="Location A",
            required_skill="Skill",
            employee=employee,
        )
        shift2 = Shift(
            id="2",
            start=datetime.combine(DAY_1, time(18, 0)),
            end=datetime.combine(DAY_1, time(22, 0)),
            location="Location B",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(one_shift_per_day).given(
            employee, shift1, shift2
        ).penalizes(1)

    def test_not_penalized_when_shifts_different_days(self):
        """Employee with shifts on different days should not be penalized."""
        employee = Employee(name="Amy")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location A",
            required_skill="Skill",
            employee=employee,
        )
        shift2 = Shift(
            id="2",
            start=DAY_START_TIME + timedelta(days=1),
            end=DAY_END_TIME + timedelta(days=1),
            location="Location B",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(one_shift_per_day).given(
            employee, shift1, shift2
        ).penalizes(0)

    def test_not_penalized_when_different_employees_same_day(self):
        """Different employees with shifts on same day should not be penalized."""
        employee1 = Employee(name="Amy")
        employee2 = Employee(name="Beth")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location A",
            required_skill="Skill",
            employee=employee1,
        )
        shift2 = Shift(
            id="2",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location B",
            required_skill="Skill",
            employee=employee2,
        )
        constraint_verifier.verify_that(one_shift_per_day).given(
            employee1, employee2, shift1, shift2
        ).penalizes(0)


# ========================================
# 10 Hours Between Shifts Tests
# ========================================

class TestAtLeast10HoursBetweenShifts:
    """Tests for the at_least_10_hours_between_two_shifts constraint."""

    def test_penalized_when_less_than_10_hours_gap(self):
        """Employee with less than 10 hours between shifts should be penalized."""
        employee = Employee(name="Amy")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,   # 9:00
            end=DAY_END_TIME,       # 17:00
            location="Location A",
            required_skill="Skill",
            employee=employee,
        )
        shift2 = Shift(
            id="2",
            start=AFTERNOON_END_TIME,  # 21:00 (4 hours after shift1 ends)
            end=DAY_START_TIME + timedelta(days=1),
            location="Location B",
            required_skill="Skill",
            employee=employee,
        )
        # Gap is 4 hours, need 10 hours, so 6 hours short = 360 minutes penalty
        constraint_verifier.verify_that(at_least_10_hours_between_two_shifts).given(
            employee, shift1, shift2
        ).penalizes_by(360)

    def test_penalized_when_no_gap(self):
        """Back-to-back shifts should be penalized by full 600 minutes."""
        employee = Employee(name="Amy")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location A",
            required_skill="Skill",
            employee=employee,
        )
        shift2 = Shift(
            id="2",
            start=DAY_END_TIME,  # Starts exactly when shift1 ends
            end=DAY_START_TIME + timedelta(days=1),
            location="Location B",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(at_least_10_hours_between_two_shifts).given(
            employee, shift1, shift2
        ).penalizes_by(600)

    def test_not_penalized_when_exactly_10_hours_gap(self):
        """Employee with exactly 10 hours between shifts should not be penalized."""
        employee = Employee(name="Amy")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,  # 17:00
            location="Location A",
            required_skill="Skill",
            employee=employee,
        )
        shift2 = Shift(
            id="2",
            start=DAY_END_TIME + timedelta(hours=10),  # 03:00 next day
            end=DAY_START_TIME + timedelta(days=1),
            location="Location B",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(at_least_10_hours_between_two_shifts).given(
            employee, shift1, shift2
        ).penalizes(0)

    def test_not_penalized_when_different_employees(self):
        """Different employees with back-to-back shifts should not be penalized."""
        employee1 = Employee(name="Amy")
        employee2 = Employee(name="Beth")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location A",
            required_skill="Skill",
            employee=employee1,
        )
        shift2 = Shift(
            id="2",
            start=AFTERNOON_END_TIME,
            end=DAY_START_TIME + timedelta(days=1),
            location="Location B",
            required_skill="Skill",
            employee=employee2,
        )
        constraint_verifier.verify_that(at_least_10_hours_between_two_shifts).given(
            employee1, employee2, shift1, shift2
        ).penalizes(0)


# ========================================
# Unavailable Employee Tests
# ========================================

class TestUnavailableEmployee:
    """Tests for the unavailable_employee constraint."""

    def test_penalized_when_shift_on_unavailable_day(self):
        """Employee scheduled on unavailable day should be penalized by shift duration."""
        employee = Employee(name="Amy", unavailable_dates={DAY_1})
        shift = Shift(
            id="1",
            start=DAY_START_TIME,  # DAY_1 at 9:00
            end=DAY_END_TIME,      # DAY_1 at 17:00
            location="Location",
            required_skill="Skill",
            employee=employee,
        )
        # 8 hours = 480 minutes
        constraint_verifier.verify_that(unavailable_employee).given(
            employee, shift
        ).penalizes_by(480)

    def test_penalized_proportionally_for_multi_day_shift(self):
        """Multi-day shift crossing unavailable day should be penalized proportionally."""
        employee = Employee(name="Amy", unavailable_dates={DAY_1})
        shift = Shift(
            id="1",
            start=DAY_START_TIME - timedelta(days=1),  # Starts day before
            end=DAY_END_TIME,                          # Ends on DAY_1
            location="Location",
            required_skill="Skill",
            employee=employee,
        )
        # Overlap with DAY_1 is from midnight to 17:00 = 17 hours = 1020 minutes
        constraint_verifier.verify_that(unavailable_employee).given(
            employee, shift
        ).penalizes_by(1020)

    def test_not_penalized_when_shift_on_different_day(self):
        """Employee scheduled on available day should not be penalized."""
        employee = Employee(name="Amy", unavailable_dates={DAY_1})
        shift = Shift(
            id="1",
            start=DAY_START_TIME + timedelta(days=1),  # DAY_2
            end=DAY_END_TIME + timedelta(days=1),
            location="Location",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(unavailable_employee).given(
            employee, shift
        ).penalizes(0)

    def test_not_penalized_when_different_employee(self):
        """Different employee (without unavailable dates) should not be penalized."""
        employee1 = Employee(name="Amy", unavailable_dates={DAY_1})
        employee2 = Employee(name="Beth")  # No unavailable dates
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Skill",
            employee=employee2,
        )
        constraint_verifier.verify_that(unavailable_employee).given(
            employee1, employee2, shift
        ).penalizes(0)

    def test_penalized_for_multiple_unavailable_days(self):
        """Shift crossing multiple unavailable days should be penalized for both."""
        employee = Employee(name="Amy", unavailable_dates={DAY_1, DAY_3})
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Skill",
            employee=employee,
        )
        # Only DAY_1 overlaps (DAY_3 is 2 days later)
        constraint_verifier.verify_that(unavailable_employee).given(
            employee, shift
        ).penalizes_by(480)


# ========================================
# Undesired Day Tests
# ========================================

class TestUndesiredDayForEmployee:
    """Tests for the undesired_day_for_employee constraint (soft)."""

    def test_penalized_when_shift_on_undesired_day(self):
        """Employee scheduled on undesired day should be penalized."""
        employee = Employee(name="Amy", undesired_dates={DAY_1})
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(undesired_day_for_employee).given(
            employee, shift
        ).penalizes_by(480)

    def test_not_penalized_when_shift_on_different_day(self):
        """Employee scheduled on non-undesired day should not be penalized."""
        employee = Employee(name="Amy", undesired_dates={DAY_1})
        shift = Shift(
            id="1",
            start=DAY_START_TIME + timedelta(days=1),
            end=DAY_END_TIME + timedelta(days=1),
            location="Location",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(undesired_day_for_employee).given(
            employee, shift
        ).penalizes(0)

    def test_not_penalized_when_different_employee(self):
        """Different employee without undesired dates should not be penalized."""
        employee1 = Employee(name="Amy", undesired_dates={DAY_1})
        employee2 = Employee(name="Beth")
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Skill",
            employee=employee2,
        )
        constraint_verifier.verify_that(undesired_day_for_employee).given(
            employee1, employee2, shift
        ).penalizes(0)


# ========================================
# Desired Day Tests
# ========================================

class TestDesiredDayForEmployee:
    """Tests for the desired_day_for_employee constraint (soft reward)."""

    def test_rewarded_when_shift_on_desired_day(self):
        """Employee scheduled on desired day should be rewarded."""
        employee = Employee(name="Amy", desired_dates={DAY_1})
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(desired_day_for_employee).given(
            employee, shift
        ).rewards_with(480)

    def test_not_rewarded_when_shift_on_different_day(self):
        """Employee scheduled on non-desired day should not be rewarded."""
        employee = Employee(name="Amy", desired_dates={DAY_1})
        shift = Shift(
            id="1",
            start=DAY_START_TIME + timedelta(days=1),
            end=DAY_END_TIME + timedelta(days=1),
            location="Location",
            required_skill="Skill",
            employee=employee,
        )
        constraint_verifier.verify_that(desired_day_for_employee).given(
            employee, shift
        ).rewards(0)

    def test_not_rewarded_when_different_employee(self):
        """Different employee without desired dates should not be rewarded."""
        employee1 = Employee(name="Amy", desired_dates={DAY_1})
        employee2 = Employee(name="Beth")
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Skill",
            employee=employee2,
        )
        constraint_verifier.verify_that(desired_day_for_employee).given(
            employee1, employee2, shift
        ).rewards(0)


# ========================================
# Balance Employee Shift Assignments Tests
# ========================================

class TestBalanceEmployeeShiftAssignments:
    """Tests for the balance_employee_shift_assignments constraint."""

    def test_no_penalty_when_no_shifts(self):
        """No shifts assigned should have zero imbalance."""
        employee1 = Employee(name="Amy")
        employee2 = Employee(name="Beth")
        constraint_verifier.verify_that(balance_employee_shift_assignments).given(
            employee1, employee2
        ).penalizes_by(0)

    def test_penalized_when_unbalanced(self):
        """Only one employee with shifts should be penalized (imbalanced)."""
        employee1 = Employee(name="Amy")
        employee2 = Employee(name="Beth")
        shift = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Skill",
            employee=employee1,
        )
        constraint_verifier.verify_that(balance_employee_shift_assignments).given(
            employee1, employee2, shift
        ).penalizes_by_more_than(0)

    def test_no_penalty_when_balanced(self):
        """Equal shifts per employee should have zero imbalance."""
        employee1 = Employee(name="Amy")
        employee2 = Employee(name="Beth")
        shift1 = Shift(
            id="1",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Skill",
            employee=employee1,
        )
        shift2 = Shift(
            id="2",
            start=DAY_START_TIME,
            end=DAY_END_TIME,
            location="Location",
            required_skill="Skill",
            employee=employee2,
        )
        constraint_verifier.verify_that(balance_employee_shift_assignments).given(
            employee1, employee2, shift1, shift2
        ).penalizes_by(0)
