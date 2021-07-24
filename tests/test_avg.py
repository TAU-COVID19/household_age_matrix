import numpy as np
from main import calc_avg,GROUP_COUNT,REPS_NUM

# Before running verify that GROUP_COUNT =16 REPS_NUM = 50
def test_avg():
    cities = [] 
    expected = np.full((GROUP_COUNT,GROUP_COUNT),49/2) 
    for i in range(REPS_NUM):
        tmp = np.full((GROUP_COUNT,GROUP_COUNT),i)
        cities.append(tmp)
    res = calc_avg(cities)
    assert (res == expected).all()
    