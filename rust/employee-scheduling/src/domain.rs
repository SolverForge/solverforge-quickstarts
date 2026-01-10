//! Domain model for Employee Scheduling Problem.

use chrono::{NaiveDate, NaiveDateTime};
use solverforge::prelude::*;
use std::collections::HashSet;

/// An employee who can be assigned to shifts.
#[problem_fact(serde)]
pub struct Employee {
    /// Index of this employee in `EmployeeSchedule.employees` for O(1) join matching.
    pub index: usize,
    pub name: String,
    pub skills: HashSet<String>,
    #[serde(rename = "unavailableDates", default)]
    pub unavailable_dates: HashSet<NaiveDate>,
    #[serde(rename = "undesiredDates", default)]
    pub undesired_dates: HashSet<NaiveDate>,
    #[serde(rename = "desiredDates", default)]
    pub desired_dates: HashSet<NaiveDate>,
    /// Sorted unavailable dates for `flatten_last` compatibility.
    /// Populated by `finalize()` from `unavailable_dates` HashSet.
    #[serde(skip)]
    pub unavailable_days: Vec<NaiveDate>,
    /// Sorted undesired dates for `flatten_last` compatibility.
    #[serde(skip)]
    pub undesired_days: Vec<NaiveDate>,
    /// Sorted desired dates for `flatten_last` compatibility.
    #[serde(skip)]
    pub desired_days: Vec<NaiveDate>,
}

impl Employee {
    pub fn new(index: usize, name: impl Into<String>) -> Self {
        Self {
            index,
            name: name.into(),
            skills: HashSet::new(),
            unavailable_dates: HashSet::new(),
            undesired_dates: HashSet::new(),
            desired_dates: HashSet::new(),
            unavailable_days: Vec::new(),
            undesired_days: Vec::new(),
            desired_days: Vec::new(),
        }
    }

    /// Populates derived Vec fields from HashSets for zero-erasure stream compatibility.
    /// Must be called after all dates have been added to HashSets.
    pub fn finalize(&mut self) {
        self.unavailable_days = self.unavailable_dates.iter().copied().collect();
        self.unavailable_days.sort();
        self.undesired_days = self.undesired_dates.iter().copied().collect();
        self.undesired_days.sort();
        self.desired_days = self.desired_dates.iter().copied().collect();
        self.desired_days.sort();
    }

    pub fn with_skills(mut self, skills: impl IntoIterator<Item = impl Into<String>>) -> Self {
        for skill in skills {
            self.skills.insert(skill.into());
        }
        self
    }
}

/// A shift that needs to be staffed by an employee.
#[planning_entity(serde)]
pub struct Shift {
    #[planning_id]
    pub id: String,
    pub start: NaiveDateTime,
    pub end: NaiveDateTime,
    pub location: String,
    #[serde(rename = "requiredSkill")]
    pub required_skill: String,
    /// Index into `EmployeeSchedule.employees` (O(1) lookup, no String cloning).
    #[planning_variable(allows_unassigned = true)]
    pub employee_idx: Option<usize>,
}

impl Shift {
    pub fn new(
        id: impl Into<String>,
        start: NaiveDateTime,
        end: NaiveDateTime,
        location: impl Into<String>,
        required_skill: impl Into<String>,
    ) -> Self {
        Self {
            id: id.into(),
            start,
            end,
            location: location.into(),
            required_skill: required_skill.into(),
            employee_idx: None,
        }
    }

    /// Returns the date of the shift start.
    pub fn date(&self) -> NaiveDate {
        self.start.date()
    }
}

/// The employee scheduling solution.
#[planning_solution(serde, constraints = "crate::constraints::create_fluent_constraints")]
#[basic_variable_config(
    entity_collection = "shifts",
    variable_field = "employee_idx",
    variable_type = "usize",
    value_range = "employees"
)]
pub struct EmployeeSchedule {
    #[problem_fact_collection]
    pub employees: Vec<Employee>,
    #[planning_entity_collection]
    pub shifts: Vec<Shift>,
    #[planning_score]
    pub score: Option<HardSoftDecimalScore>,
    #[serde(rename = "solverStatus", skip_serializing_if = "Option::is_none")]
    pub solver_status: Option<String>,
}

impl EmployeeSchedule {
    pub fn new(employees: Vec<Employee>, shifts: Vec<Shift>) -> Self {
        Self {
            employees,
            shifts,
            score: None,
            solver_status: None,
        }
    }

}
