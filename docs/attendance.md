# Nepal Compliance: Attendance & Reporting

This document provides a comprehensive guide to the specialized attendance tools implemented in the Nepal Compliance module. These tools are designed for BS (Bikram Sambat) date compliance and high-visibility monitoring.

---

## 1. Monthly Attendance Sheet BS (Report)

The **Monthly Attendance Sheet BS** is a grid-based report tailored for the Nepali calendar system.

### Header & UI Layout
- **Nepali Dates**: Columns are labeled in the format `DD MON` (e.g., `01 Baisakh`) based on the BS month.
- **Column Priority**:
  1. **Employee Name**: Primary identifier.
  2. **Worked/Target**: Displays a summary of total hours worked vs. expected hours for the month.
  3. **Daily Slots**: Individual columns for every day in the BS month.
  4. **Employee ID**: Moved to the end of the report for a cleaner focus on names.

### Status Indicators (Pills)
The report uses color-coded "pills" for daily status:
- **P (Present)**: Green. Shows worked hours (e.g., `8h`).
- **HD/P (Half Day)**: Yellow/Orange. Contributes 4.0 hours to the target.
- **WO (Weekly Off)**: Grey.
- **Hol (Holiday)**: Grey.
- **Lv (On Leave)**: Blue.
- **Ab (Absent)**: Red.
- **WFH (Work From Home)**: Teal.

### Calculations Logic
- **Target Hours**:
    - **Standard Day**: 8.0 hours added to the target.
    - **Half Day**: 4.0 hours added to the target.
    - **Holidays/Weekly Offs**: 0.0 hours added to the target.
    - **Leaves/Absent**: 0.0 hours added to the target.
- **Weekly Off Work**: If an employee performs work on a "Weekly Off" day, the worked hours are tracked and logged, but **0.0 hours** are added to the target, ensuring overtime is handled correctly by the payroll system.
- **Worked Hours**: Sum of all `Employee Checkin` durations mapped to the day.

### Permissions & Security
- **HR Managers / Administrators**: Can view records for the entire company.
- **Attendance Report Viewer**: Any user assigned this role can view records for the entire company (used for non-employee stakeholders).
- **Standard Employees**: 
    - Can only view their own attendance.
    - If they are a supervisor, they can view the attendance of their direct and indirect subordinates via a recursive hierarchical lookup.
    - Permission checks are strictly enforced in the backend.

---

## 2. Live Attendance Board (Page)

The **Live Attendance Board** is a real-time Kanban dashboard for daily monitoring.

### Kanban Columns
1. **Pending (Red)**: Employees who have not yet logged a check-in for the current day.
2. **Active (Green)**: Employees who are currently on shift.
3. **Checked Out (Blue)**: Employees who have completed their shift.
4. **On Leave - Today (Purple)**: Employees with an approved Leave Application for today.
5. **Upcoming Leaves (Orange)**: Employees with approved leaves starting in the near future.

### Core Features
- **Strict Checkout Logic**: An employee is only moved to the "Checked Out" column if their *latest* log type is explicitly marked as `OUT`.
- **Department Grouping**: Multi-level folding system. You can collapse or expand department groups to focus on specific teams.
- **Real-time Clock**: A ticking HH:mm:ss clock synchronized with the server time.
- **Nepali Date Display**: The dashboard header displays today's date in full BS format.
- **Fold State**: The dashboard supports folding/unfolding departments for vertical focus.

### Permissions
- **Access**: Assigned to the `Employee` and `Attendance Report Viewer` roles. 
- **Visibility**: This dashboard is public for all employees to see company-wide real-time status, facilitating better team coordination. Non-employees with the `Attendance Report Viewer` role can also view this page.

### Interaction
- **Hover/Title**: Hovering over a card in the "Completed" or "Active" list shows a detailed timeline of all punches for that day (e.g., `09:30 (IN) -> 13:00 (OUT) -> 14:00 (IN)`).
- **Refresh**: Use the **Refresh** button in the top right to trigger a manual data sweep without reloading the whole page.
