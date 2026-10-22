"""Dependency-free deterministic planning calculations."""
import math
def simulate_resource_runway(days_to_simulate, daily_burn_rate, current_stock):
    if isinstance(days_to_simulate,bool) or not isinstance(days_to_simulate,int) or not 0<=days_to_simulate<=3650:
        raise ValueError("days_to_simulate muss zwischen 0 und 3650 liegen.")
    for name,value in (("daily_burn_rate",daily_burn_rate),("current_stock",current_stock)):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or value>1e15:
            raise ValueError(name+" muss eine endliche, nichtnegative Zahl sein.")
    stock=float(current_stock); threshold=stock*.2; timeline=[]
    for day in range(1,days_to_simulate+1):
        stock=max(0.0,stock-float(daily_burn_rate))
        timeline.append({"day":day,"remaining_stock":round(stock,6),"status":"KRITISCH" if stock<=threshold else "STABIL"})
        if stock==0: break
    return timeline
