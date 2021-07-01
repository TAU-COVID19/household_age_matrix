import numpy as np
from main import calc_sem,generate_cities,GROUP_COUNT,REPS_NUM

def test_sem1():
    cities = [] 
    expected = np.full((GROUP_COUNT,GROUP_COUNT),0) 
    for i in range(REPS_NUM):
        tmp = np.full((GROUP_COUNT,GROUP_COUNT),3)
        cities.append(tmp)
    res = calc_sem(cities)
    assert (res == expected).all()

def test_sem2():
    city_name = 'Atlit'
    expected = np.full((GROUP_COUNT,GROUP_COUNT),np.nan)
    cities = generate_cities(city_name)
    res = calc_sem(cities)
    assert not(res == expected).any()
    