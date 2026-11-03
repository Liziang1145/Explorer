"""轻量 One Euro 滤波器，用于 VR 连续位置目标。

只依赖 Python 标准库；输入位置单位为 m，时间戳单位为 s。
"""

import math


class LowPassFilter:
    def __init__(self, initial):
        self.value = float(initial)

    def __call__(self, value, alpha):
        self.value += alpha * (float(value) - self.value)
        return self.value


class OneEuroFilter:
    """单通道 One Euro：速度越快，截止频率越高，降低快速跟随延迟。"""

    def __init__(self, initial=0.0, min_cutoff=1.2, beta=8.0,
                 d_cutoff=1.0, default_dt=0.05):
        if min_cutoff <= 0.0 or d_cutoff <= 0.0 or beta < 0.0:
            raise ValueError("One Euro 参数必须满足 min_cutoff>0、d_cutoff>0、beta>=0")
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.default_dt = float(default_dt)
        self.x_filter = LowPassFilter(initial)
        self.dx_filter = LowPassFilter(0.0)
        self.last_time = None
        self.last_raw = float(initial)
        self.last_cutoff = self.min_cutoff

    @staticmethod
    def alpha(cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, value, timestamp):
        value = float(value)
        timestamp = float(timestamp)
        if not math.isfinite(value) or not math.isfinite(timestamp):
            raise ValueError("One Euro 输入和时间戳必须为有限数")
        dt = self.default_dt if self.last_time is None else timestamp - self.last_time
        # 重复时间戳或断流后的首拍不放大导数；控制周期恢复后继续使用新数据。
        if not math.isfinite(dt) or dt <= 0.0 or dt > 0.25:
            dt = self.default_dt
        self.last_time = timestamp
        derivative = (value - self.last_raw) / dt
        self.last_raw = value
        derivative_hat = self.dx_filter(
            derivative, self.alpha(self.d_cutoff, dt))
        self.last_cutoff = self.min_cutoff + self.beta * abs(derivative_hat)
        return self.x_filter(value, self.alpha(self.last_cutoff, dt))


class OneEuroFilter3:
    """XYZ 三通道版本，各轴独立滤波，共用参数和调用时间戳。"""

    def __init__(self, initial=(0.0, 0.0, 0.0), **kwargs):
        if len(initial) != 3:
            raise ValueError("OneEuroFilter3 的初值必须为三维位置")
        self.filters = [OneEuroFilter(value, **kwargs) for value in initial]

    def __call__(self, position, timestamp):
        if len(position) != 3:
            raise ValueError("OneEuroFilter3 的输入必须为三维位置")
        return tuple(f(value, timestamp) for f, value in zip(self.filters, position))
