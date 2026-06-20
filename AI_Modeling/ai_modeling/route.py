# -*- coding: utf-8 -*-
"""
路线（Route）生成与沿路线布置组件
"""
import math


class Route:
    """3D 路线，支持直线/折线/圆弧等，可等距采样"""

    def __init__(self, points, route_type='polyline'):
        """
        points: [(x,y,z), ...] 路线控制点
        route_type: 'line' | 'polyline' | 'arc'
        """
        self.points = [tuple(float(v) for v in p) for p in points]
        self.route_type = route_type
        self._cached_length = None
        self._cached_samples = None

    @classmethod
    def line(cls, start, end):
        """从起点到终点的直线"""
        return cls([start, end], route_type='line')

    @classmethod
    def from_axis(cls, start, length, axis='x'):
        """从起点沿某轴生成直线"""
        sx, sy, sz = start
        length = float(length)
        if axis == 'x':
            end = (sx + length, sy, sz)
        elif axis == 'y':
            end = (sx, sy + length, sz)
        elif axis == 'z':
            end = (sx, sy, sz + length)
        else:
            end = (sx + length, sy, sz)
        return cls.line(start, end)

    def total_length(self):
        """路线总长度"""
        if self._cached_length is not None:
            return self._cached_length
        total = 0.0
        for i in range(len(self.points) - 1):
            total += self._dist(self.points[i], self.points[i + 1])
        self._cached_length = total
        return total

    @staticmethod
    def _dist(a, b):
        return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))

    def sample_points(self, spacing=None, count=None, include_end=True):
        """
        沿路线等距采样点。
        spacing: 间距；count: 点数；二选一。
        include_end: 是否包含终点（当 spacing 不能整除时）。
        返回 [(x,y,z), ...]
        """
        if not self.points:
            return []
        length = self.total_length()
        if length <= 0:
            return [self.points[0]]

        if spacing is not None and spacing > 0:
            count = int(length // spacing) + 1
            if include_end and length % spacing != 0:
                count += 1
        elif count is not None and count > 0:
            spacing = length / (count - 1) if count > 1 else 0
        else:
            return [self.points[0]]

        if count == 1:
            return [self.points[0]]

        samples = []
        target_distances = [i * spacing for i in range(count)]
        if include_end and not math.isclose(target_distances[-1], length, rel_tol=1e-6):
            target_distances.append(length)

        current_seg = 0
        current_seg_start_dist = 0.0
        for d in target_distances:
            d = min(d, length)
            # 找到 d 所在的线段
            while current_seg < len(self.points) - 1:
                seg_len = self._dist(self.points[current_seg], self.points[current_seg + 1])
                if current_seg_start_dist + seg_len >= d or math.isclose(current_seg_start_dist + seg_len, d, rel_tol=1e-6):
                    break
                current_seg_start_dist += seg_len
                current_seg += 1

            if current_seg >= len(self.points) - 1:
                samples.append(self.points[-1])
                continue

            seg_len = self._dist(self.points[current_seg], self.points[current_seg + 1])
            if seg_len <= 0:
                samples.append(self.points[current_seg])
                continue

            t = (d - current_seg_start_dist) / seg_len
            t = max(0.0, min(1.0, t))
            a = self.points[current_seg]
            b = self.points[current_seg + 1]
            p = tuple(a[i] + t * (b[i] - a[i]) for i in range(3))
            samples.append(p)

        return samples

    def __repr__(self):
        return f"Route({self.route_type}, {len(self.points)} points, length={self.total_length():.2f})"


def generate_linear_route(start, end):
    """生成直线路线"""
    return Route.line(start, end)


def sample_route_for_components(route, spacing=None, count=None, include_end=True):
    """沿路线采样布置点"""
    return route.sample_points(spacing=spacing, count=count, include_end=include_end)
