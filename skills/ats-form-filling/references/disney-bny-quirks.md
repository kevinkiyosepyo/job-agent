# Disney + BNY ATS Quirks

Session-derived details that are useful across future ATS sessions.

## Dropdown-backed fields must bind real options

Observed on Disney Workday and BNY Oracle flows:
- visible typed text can remain while the field is still logically empty
- salary, source, school, country, and consent prompts often need a true option click
- nested prompts can require two levels: category first, then a concrete option

### Examples
- `Social Media` was not sufficient by itself; Disney required a concrete child option such as `Instagram` or `Facebook`.
- BNY compensation and source fields behaved like dropdown-backed prompts even when text entry looked possible.

## Date widgets can reject visible values

Observed on Disney:
- `From` showed `04/2025` on screen but the form still flagged the field as required until the control fully accepted the date.
- When a date error remains, assume the widget binding has not committed and re-drive the date control.

## Portal verification patterns

### BNY Oracle
A successful submit can be verified from candidate home when the application appears under active applications with:
- exact role title
- requisition number
- applied date
- status such as `Under Consideration`

### Disney Workday
The candidate flow can resume cleanly once the top-right signed-in state is present. If the user signs in manually, re-check the current step before repeating account-recovery work.

## Kevin-specific job defaults seen in live use

- compensation target: `$20/hour` or `$20k annual` when required
- source default: `Social Media`, then concrete platform `Instagram` or `Facebook` when required
- education timing: `B.S. Data Science`, `Sep 2024 - May 2028`
- application address: `10256 Eagle Nest Ct, Fairfax, VA 22032`
