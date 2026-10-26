"""Two-decimal measurement values; integer counters stay exact."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
import math


def metric_value(value):
    if not isinstance(value, float):
        return value
    if not math.isfinite(value):
        raise ValueError('Non-finite monitoring value')
    with localcontext() as context:
        context.rounding = ROUND_HALF_UP
        text = format(Decimal(str(value)), '.2f')
    return '0.00' if text == '-0.00' else text
