from datetime import date, datetime
import re

import logging

_logger = logging.getLogger(__name__)

## CALCULATE AGE BASED ON birthday INPUT - HELPER FUNCTION 
def calc_age(birthdate_in):
    _logger.info("type(birthdate_in) = %s", type(birthdate_in))
    if type(birthdate_in) == str:
        birthdate = datetime.strptime(birthdate_in, '%Y-%m-%d')
    else:
        birthdate = birthdate_in
    today = date.today()
    # use a boolean representing if today's day/month precedes the birth day/month
    one_or_zero = ((today.month, today.day) < (birthdate.month, birthdate.day))
    year_difference = today.year - birthdate.year
    age = year_difference - one_or_zero
    _logger.info("## ## ## ## RETURNING %s AS age", age)
    return age


## VALIDATE EVENT ATTENDEE
## BY GENDER SETTINGS AND AGE
def fail_checks_for_attendee_at_event(a10d_gender, a10d_gender_pref_female, a10d_gender_pref_male, a10d_birthdate, event_name_str):
    fails = ''
    ## CURRENTLY ASSUMING 'Singles' IN event_name_str
    gender_match = re.search("Women" , event_name_str)
    if gender_match:
        gender_match = 'F'  ## 'Women' text in event titles; 'F' stored in Db
        if gender_match != a10d_gender or a10d_gender_pref_male != True:
            fails = "Gender settings"
    else:
        gender_match = re.search("Men" , event_name_str)
        if gender_match:
            gender_match = 'M'
            if gender_match != a10d_gender or a10d_gender_pref_female != True:
                fails = "Gender settings"
        ##  else:  SKIPPED
        #     ## CHANGE IF BUSINESS 'TURNS' GAY
        #     fails = "Entire Event setup"
        #     return fails  ## FATAL ERROR, FOR NOW
        
    
    ## MATCH ON '[0-9][0-9]s', group output, lose last char, and convert to int
    decade_match = int(re.search('\d\ds', event_name_str).group()[:-1])
    _logger.info("## ## ## decade_match = %s", decade_match)
    _logger.info("## ## ## type(decade_match) = %s", type(decade_match))
    if decade_match == 20:
        min_age = 21
        max_age = decade_match + 15
    if decade_match > 20 and decade_match < 70:
        min_age = decade_match - 6
        max_age = decade_match + 15
    if decade_match == 70:
        min_age = decade_match - 6
        max_age = 500  ## ARBITRARY LARGE NUMBER
    
    a10d_age = calc_age(a10d_birthdate)
    if a10d_age < min_age or a10d_age > max_age:
        if fails:
            fails += " and Birthdate"
        else:
            fails = "Birthdate"

    _logger.info("## ## ## ## RETURNING fails = %s", fails)
    return fails
