from solverforge_legacy.solver.test import ConstraintVerifier

from meeting_scheduling.domain import (
    Attendance,
    Meeting,
    MeetingAssignment,
    MeetingSchedule,
    Person,
    PreferredAttendance,
    RequiredAttendance,
    Room,
    TimeGrain,
)
from meeting_scheduling.constraints import (
    define_constraints,
    room_conflict,
    avoid_overtime,
    required_attendance_conflict,
    required_room_capacity,
    start_and_end_on_same_day,
    required_and_preferred_attendance_conflict,
    preferred_attendance_conflict,
    room_stability,
)


DEFAULT_TIME_GRAINS = [
    TimeGrain(
        id=str(i + 1), grain_index=i, day_of_year=1, starting_minute_of_day=480 + i * 15
    )
    for i in range(8)
]

DEFAULT_ROOM = Room(id="1", name="Room 1", capacity=10)
SMALL_ROOM = Room(id="2", name="Small Room", capacity=1)
LARGE_ROOM = Room(id="3", name="Large Room", capacity=2)
ROOM_A = Room(id="4", name="Room A", capacity=10)
ROOM_B = Room(id="5", name="Room B", capacity=10)


constraint_verifier = ConstraintVerifier.build(
    define_constraints, MeetingSchedule, MeetingAssignment
)


def test_room_conflict_unpenalized():
    """Test that no penalty is applied when meetings in the same room do not overlap."""
    meeting1 = create_meeting(1)
    left_assignment = create_meeting_assignment(
        0, meeting1, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM
    )

    meeting2 = create_meeting(2)
    right_assignment = create_meeting_assignment(
        1, meeting2, DEFAULT_TIME_GRAINS[4], DEFAULT_ROOM
    )

    constraint_verifier.verify_that(room_conflict).given(
        left_assignment, right_assignment
    ).penalizes(0)


def test_room_conflict_penalized():
    """Test that a penalty is applied when meetings in the same room overlap."""
    meeting1 = create_meeting(1)
    left_assignment = create_meeting_assignment(
        0, meeting1, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM
    )

    meeting2 = create_meeting(2)
    right_assignment = create_meeting_assignment(
        1, meeting2, DEFAULT_TIME_GRAINS[2], DEFAULT_ROOM
    )

    constraint_verifier.verify_that(room_conflict).given(
        left_assignment, right_assignment
    ).penalizes_by(2)


def test_avoid_overtime_unpenalized():
    """Test that no penalty is applied when a meeting fits within available time grains (no overtime)."""
    meeting = create_meeting(1)
    meeting_assignment = create_meeting_assignment(
        0, meeting, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM
    )

    constraint_verifier.verify_that(avoid_overtime).given(
        meeting_assignment, *DEFAULT_TIME_GRAINS
    ).penalizes(0)


def test_avoid_overtime_penalized():
    """Test that a penalty is applied when a meeting exceeds available time grains (overtime)."""
    meeting = create_meeting(1)
    meeting_assignment = create_meeting_assignment(
        0, meeting, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM
    )

    constraint_verifier.verify_that(avoid_overtime).given(
        meeting_assignment
    ).penalizes_by(3)


def test_required_attendance_conflict_unpenalized():
    """Test that no penalty is applied when a person does not have overlapping required meetings."""
    person = create_person(1)

    left_meeting = create_meeting(1, duration=2)
    required_attendance1 = create_required_attendance(0, person, left_meeting)

    right_meeting = create_meeting(2, duration=2)
    required_attendance2 = create_required_attendance(1, person, right_meeting)

    left_assignment = create_meeting_assignment(
        0, left_meeting, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM
    )
    right_assignment = create_meeting_assignment(
        1, right_meeting, DEFAULT_TIME_GRAINS[2], DEFAULT_ROOM
    )

    constraint_verifier.verify_that(required_attendance_conflict).given(
        required_attendance1, required_attendance2, left_assignment, right_assignment
    ).penalizes(0)


def test_required_attendance_conflict_penalized():
    """Test that a penalty is applied when a person has overlapping required meetings."""
    person = create_person(1)

    left_meeting = create_meeting(1, duration=2)
    required_attendance1 = create_required_attendance(0, person, left_meeting)

    right_meeting = create_meeting(2, duration=2)
    required_attendance2 = create_required_attendance(1, person, right_meeting)

    left_assignment = create_meeting_assignment(
        0, left_meeting, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM
    )
    right_assignment = create_meeting_assignment(
        1, right_meeting, DEFAULT_TIME_GRAINS[1], DEFAULT_ROOM
    )

    constraint_verifier.verify_that(required_attendance_conflict).given(
        required_attendance1, required_attendance2, left_assignment, right_assignment
    ).penalizes_by(1)


def test_required_room_capacity_unpenalized():
    """Test that no penalty is applied when the room has enough capacity for all required and preferred attendees."""
    person1 = create_person(1)
    person2 = create_person(2)

    meeting = create_meeting(1, duration=2)
    create_required_attendance(0, person1, meeting)
    create_preferred_attendance(1, person2, meeting)

    meeting_assignment = create_meeting_assignment(
        0, meeting, DEFAULT_TIME_GRAINS[0], LARGE_ROOM
    )

    constraint_verifier.verify_that(required_room_capacity).given(
        meeting_assignment
    ).penalizes(0)


def test_required_room_capacity_penalized():
    """Test that a penalty is applied when the room does not have enough capacity for all required and preferred attendees."""
    person1 = create_person(1)
    person2 = create_person(2)

    meeting = create_meeting(1, duration=2)
    create_required_attendance(0, person1, meeting)
    create_preferred_attendance(1, person2, meeting)

    meeting_assignment = create_meeting_assignment(
        0, meeting, DEFAULT_TIME_GRAINS[0], SMALL_ROOM
    )

    constraint_verifier.verify_that(required_room_capacity).given(
        meeting_assignment
    ).penalizes_by(1)


def test_start_and_end_on_same_day_unpenalized():
    """Test that no penalty is applied when a meeting starts and ends on the same day."""
    # Need custom time grains with day_of_year=0 (DEFAULT_TIME_GRAINS use day_of_year=1)
    start_time_grain = TimeGrain(
        id="1", grain_index=0, day_of_year=0, starting_minute_of_day=480
    )
    end_time_grain = TimeGrain(
        id="2", grain_index=3, day_of_year=0, starting_minute_of_day=525
    )  # Same day

    meeting = create_meeting(1)
    meeting_assignment = create_meeting_assignment(
        0, meeting, start_time_grain, DEFAULT_ROOM
    )

    constraint_verifier.verify_that(start_and_end_on_same_day).given(
        meeting_assignment, end_time_grain
    ).penalizes(0)


def test_start_and_end_on_same_day_penalized():
    """Test that a penalty is applied when a meeting starts and ends on different days."""
    # Need custom time grains to test different days (start=day 0, end=day 1)
    start_time_grain = TimeGrain(
        id="1", grain_index=0, day_of_year=0, starting_minute_of_day=480
    )
    end_time_grain = TimeGrain(
        id="2", grain_index=3, day_of_year=1, starting_minute_of_day=525
    )  # Different day

    meeting = create_meeting(1)
    meeting_assignment = create_meeting_assignment(
        0, meeting, start_time_grain, DEFAULT_ROOM
    )

    constraint_verifier.verify_that(start_and_end_on_same_day).given(
        meeting_assignment, end_time_grain
    ).penalizes_by(1)


def test_multiple_constraint_violations():
    """Test that multiple constraints can be violated simultaneously."""
    person = create_person(1)

    left_meeting = create_meeting(1)
    required_attendance1 = create_required_attendance(0, person, left_meeting)
    left_assignment = create_meeting_assignment(
        0, left_meeting, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM
    )

    right_meeting = create_meeting(2)
    required_attendance2 = create_required_attendance(1, person, right_meeting)
    right_assignment = create_meeting_assignment(
        1, right_meeting, DEFAULT_TIME_GRAINS[2], DEFAULT_ROOM
    )

    constraint_verifier.verify_that(room_conflict).given(
        left_assignment, right_assignment
    ).penalizes_by(2)
    constraint_verifier.verify_that(required_attendance_conflict).given(
        required_attendance1, required_attendance2, left_assignment, right_assignment
    ).penalizes_by(2)


### Helper functions ###


def create_meeting(id, topic="Meeting", duration=4):
    """Helper to create a meeting with standard parameters."""
    return Meeting(id=str(id), topic=f"{topic} {id}", duration_in_grains=duration)


def create_meeting_assignment(id, meeting, time_grain, room):
    """Helper to create a meeting assignment."""
    return MeetingAssignment(
        id=str(id), meeting=meeting, starting_time_grain=time_grain, room=room
    )


def create_person(id):
    """Helper to create a person."""
    return Person(id=str(id), full_name=f"Person {id}")


def create_required_attendance(id, person, meeting):
    """Helper to create and link required attendance."""
    attendance = RequiredAttendance(id=str(id), person=person, meeting_id=meeting.id)
    meeting.required_attendances = [attendance]
    return attendance


def create_preferred_attendance(id, person, meeting):
    """Helper to create and link preferred attendance."""
    attendance = PreferredAttendance(id=str(id), person=person, meeting_id=meeting.id)
    meeting.preferred_attendances = [attendance]
    return attendance


def create_attendance(id, person, meeting):
    """Helper to create an Attendance object for room_stability constraint."""
    return Attendance(id=str(id), person=person, meeting_id=meeting.id)


# ========================================
# Required and Preferred Attendance Conflict Tests
# ========================================


def test_required_and_preferred_attendance_conflict_unpenalized():
    """Test no penalty when required and preferred meetings don't overlap."""
    person = create_person(1)

    # Meeting 1: grain 0-3 (duration=4), person required
    meeting1 = create_meeting(1, duration=4)
    attendance1 = create_required_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM)

    # Meeting 2: grain 4-7 (duration=4), person preferred
    meeting2 = create_meeting(2, duration=4)
    attendance2 = create_preferred_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[4], ROOM_A)

    constraint_verifier.verify_that(required_and_preferred_attendance_conflict).given(
        attendance1, attendance2, assignment1, assignment2
    ).penalizes_by(0)


def test_required_and_preferred_attendance_conflict_penalized():
    """Test penalty when person required at one meeting and preferred at overlapping meeting."""
    person = create_person(1)

    # Meeting 1: grain 0-3 (duration=4), person required
    meeting1 = create_meeting(1, duration=4)
    attendance1 = create_required_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM)

    # Meeting 2: grain 2-5 (duration=4), person preferred, overlaps grains 2-3 (2 grains)
    meeting2 = create_meeting(2, duration=4)
    attendance2 = create_preferred_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[2], ROOM_A)

    # Overlap: grains 2-3 = 2 grains
    constraint_verifier.verify_that(required_and_preferred_attendance_conflict).given(
        attendance1, attendance2, assignment1, assignment2
    ).penalizes_by(2)


# ========================================
# Preferred Attendance Conflict Tests
# ========================================


def test_preferred_attendance_conflict_unpenalized():
    """Test no penalty when preferred attendee has non-overlapping meetings."""
    person = create_person(1)

    # Meeting 1: grain 0-3 (duration=4), person preferred
    meeting1 = create_meeting(1, duration=4)
    attendance1 = create_preferred_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM)

    # Meeting 2: grain 4-7 (duration=4), person preferred
    meeting2 = create_meeting(2, duration=4)
    attendance2 = create_preferred_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[4], ROOM_A)

    constraint_verifier.verify_that(preferred_attendance_conflict).given(
        attendance1, attendance2, assignment1, assignment2
    ).penalizes_by(0)


def test_preferred_attendance_conflict_penalized():
    """Test penalty when person preferred at multiple overlapping meetings."""
    person = create_person(1)

    # Meeting 1: grain 0-3 (duration=4), person preferred
    meeting1 = create_meeting(1, duration=4)
    attendance1 = create_preferred_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[0], DEFAULT_ROOM)

    # Meeting 2: grain 1-4 (duration=4), person preferred, overlaps grains 1-3 (3 grains)
    meeting2 = create_meeting(2, duration=4)
    attendance2 = create_preferred_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[1], ROOM_A)

    # Overlap: grains 1-3 = 3 grains
    constraint_verifier.verify_that(preferred_attendance_conflict).given(
        attendance1, attendance2, assignment1, assignment2
    ).penalizes_by(3)


# ========================================
# Room Stability Tests
# ========================================


def test_room_stability_same_room_no_penalty():
    """
    Test that no penalty is applied when a person attends consecutive
    meetings in the same room (stability is maintained).
    """
    person = create_person(1)

    # Meeting 1: time grain 0-1 (duration=2) in ROOM_A
    meeting1 = create_meeting(1, duration=2)
    create_required_attendance(0, person, meeting1)
    att1 = create_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[0], ROOM_A)

    # Meeting 2: time grain 3-4 (duration=2) in ROOM_A (same room, gap of 1)
    meeting2 = create_meeting(2, duration=2)
    create_required_attendance(1, person, meeting2)
    att2 = create_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[3], ROOM_A)

    # Same room should not penalize
    constraint_verifier.verify_that(room_stability).given(
        att1, att2, assignment1, assignment2
    ).penalizes(0)


def test_room_stability_different_room_with_required_attendance():
    """
    Test that a penalty is applied when a person with required attendance
    has to change rooms between closely scheduled meetings.
    Weighted penalty: back-to-back switches cost more than switches with gaps.
    """
    person = create_person(1)

    # Meeting 1: time grain 0-1 (duration=2) in ROOM_A
    left_grain_index = 0
    left_duration = 2
    meeting1 = create_meeting(1, duration=left_duration)
    create_required_attendance(0, person, meeting1)
    att1 = create_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[left_grain_index], ROOM_A)

    # Meeting 2: time grain 3-4 (duration=2) in ROOM_B (different room)
    right_grain_index = 3
    meeting2 = create_meeting(2, duration=2)
    create_required_attendance(1, person, meeting2)
    att2 = create_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[right_grain_index], ROOM_B)

    # Weighted penalty: 3 - gap, where gap = right_grain - left_duration - left_grain
    gap = right_grain_index - left_duration - left_grain_index
    expected_penalty = 3 - gap

    constraint_verifier.verify_that(room_stability).given(
        att1, att2, assignment1, assignment2
    ).penalizes_by(expected_penalty)


def test_room_stability_different_room_with_preferred_attendance():
    """
    Test that a penalty is applied when a person with preferred attendance
    has to change rooms between closely scheduled meetings.
    Weighted penalty applies to preferred attendance too.
    """
    person = create_person(1)

    # Meeting 1: time grain 0-1 (duration=2) in ROOM_A
    left_grain_index = 0
    left_duration = 2
    meeting1 = create_meeting(1, duration=left_duration)
    create_preferred_attendance(0, person, meeting1)
    att1 = create_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[left_grain_index], ROOM_A)

    # Meeting 2: time grain 3-4 (duration=2) in ROOM_B (different room)
    right_grain_index = 3
    meeting2 = create_meeting(2, duration=2)
    create_preferred_attendance(1, person, meeting2)
    att2 = create_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[right_grain_index], ROOM_B)

    # Weighted penalty: 3 - gap
    gap = right_grain_index - left_duration - left_grain_index
    expected_penalty = 3 - gap

    constraint_verifier.verify_that(room_stability).given(
        att1, att2, assignment1, assignment2
    ).penalizes_by(expected_penalty)


def test_room_stability_mixed_attendance_types():
    """
    Test that room stability penalty applies when mixing required and preferred
    attendance types for the same person.
    """
    person = create_person(1)

    # Meeting 1 with required attendance
    left_grain_index = 0
    left_duration = 2
    meeting1 = create_meeting(1, duration=left_duration)
    create_required_attendance(0, person, meeting1)
    att1 = create_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[left_grain_index], ROOM_A)

    # Meeting 2 with preferred attendance
    right_grain_index = 3
    meeting2 = create_meeting(2, duration=2)
    create_preferred_attendance(1, person, meeting2)
    att2 = create_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[right_grain_index], ROOM_B)

    # Weighted penalty: 3 - gap
    gap = right_grain_index - left_duration - left_grain_index
    expected_penalty = 3 - gap

    constraint_verifier.verify_that(room_stability).given(
        att1, att2, assignment1, assignment2
    ).penalizes_by(expected_penalty)


def test_room_stability_far_apart_meetings_no_penalty():
    """
    Test that no penalty is applied when meetings are far apart in time,
    even if they're in different rooms.
    """
    person = create_person(1)

    # Meeting 1: time grain 0-1 (duration=2) in ROOM_A
    meeting1 = create_meeting(1, duration=2)
    create_required_attendance(0, person, meeting1)
    att1 = create_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[0], ROOM_A)

    # Meeting 2: time grain 6-7 (duration=2) in ROOM_B
    # gap = grain_index(6) - duration_in_grains(2) - grain_index(0) = 6 - 2 - 0 = 4 > 2
    meeting2 = create_meeting(2, duration=2)
    create_required_attendance(1, person, meeting2)
    att2 = create_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[6], ROOM_B)

    # Far apart meetings should not penalize even with room change
    constraint_verifier.verify_that(room_stability).given(
        att1, att2, assignment1, assignment2
    ).penalizes(0)


def test_room_stability_different_people_no_penalty():
    """
    Test that no penalty is applied when different people have meetings
    in different rooms (room stability is per-person).
    """
    person1 = create_person(1)
    person2 = create_person(2)

    # Person 1's meeting in ROOM_A
    meeting1 = create_meeting(1, duration=2)
    create_required_attendance(0, person1, meeting1)
    att1 = create_attendance(0, person1, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[0], ROOM_A)

    # Person 2's meeting in ROOM_B (different person, should not affect stability)
    meeting2 = create_meeting(2, duration=2)
    create_required_attendance(1, person2, meeting2)
    att2 = create_attendance(1, person2, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[3], ROOM_B)

    # Different people should not trigger room stability penalty
    constraint_verifier.verify_that(room_stability).given(
        att1, att2, assignment1, assignment2
    ).penalizes(0)


def test_room_stability_back_to_back_highest_penalty():
    """
    Test that back-to-back room switches (gap=0) incur the highest penalty (3).
    This verifies the weighted penalty gradient: closer switches cost more.
    """
    person = create_person(1)

    # Meeting 1: grain 0-1 (duration=2) in ROOM_A
    left_grain_index = 0
    left_duration = 2
    meeting1 = create_meeting(1, duration=left_duration)
    create_required_attendance(0, person, meeting1)
    att1 = create_attendance(0, person, meeting1)
    assignment1 = create_meeting_assignment(0, meeting1, DEFAULT_TIME_GRAINS[left_grain_index], ROOM_A)

    # Meeting 2: grain 2-3 (immediately after) in ROOM_B
    right_grain_index = 2  # Starts right after meeting1 ends
    meeting2 = create_meeting(2, duration=2)
    create_required_attendance(1, person, meeting2)
    att2 = create_attendance(1, person, meeting2)
    assignment2 = create_meeting_assignment(1, meeting2, DEFAULT_TIME_GRAINS[right_grain_index], ROOM_B)

    # gap = 2 - 2 - 0 = 0, penalty = 3 - 0 = 3
    gap = right_grain_index - left_duration - left_grain_index
    expected_penalty = 3 - gap
    assert gap == 0, f"Test setup error: expected gap=0, got {gap}"
    assert expected_penalty == 3, f"Test setup error: expected penalty=3, got {expected_penalty}"

    constraint_verifier.verify_that(room_stability).given(
        att1, att2, assignment1, assignment2
    ).penalizes_by(expected_penalty)
