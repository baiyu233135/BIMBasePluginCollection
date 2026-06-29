# -*- coding: utf-8 -*-
"""
路线（Route）生成与沿路线布置组件
v1.1: 新增 sample_frames（采样点+切线）与 ArcRoute 圆弧路线
"""
import math


class Route:
    """3D 路线，支持直线/折线，可等距采样"""

    def __init__(self, points, route_type='polyline'):
        """
        points: [(x,y,z), ...] 路线控制点
        route_type: 'line' | 'polyline'
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

    @staticmethod
    def _normalize(v):
        length = math.sqrt(sum(x * x for x in v))
        if length == 0:
            return (0.0, 0.0, 1.0)
        return tuple(x / length for x in v)

    def sample_points(self, spacing=None, count=None, include_end=True):
        """
        沿路线等距采样点。
        spacing: 间距；count: 点数；二选一。
        include_end: 是否包含终点（当 spacing 不能整除时）。
        返回 [(x,y,z), ...]
        """
        return [p for p, _ in self.sample_frames(spacing=spacing, count=count, include_end=include_end)]

    def sample_frames(self, spacing=None, count=None, include_end=True):
        """
        沿路线等距采样点与切线。
        返回 [((x,y,z), (tx,ty,tz)), ...]
        """
        if not self.points:
            return []
        length = self.total_length()
        if length <= 0:
            return [(self.points[0], (1.0, 0.0, 0.0))]

        if spacing is not None and spacing > 0:
            count = int(length // spacing) + 1
            if include_end and not math.isclose(length % spacing, 0, rel_tol=1e-6):
                count += 1
        elif count is not None and count > 0:
            spacing = length / (count - 1) if count > 1 else 0
        else:
            return [(self.points[0], self._normalize(self._segment_dir(0)))]

        if count == 1:
            return [(self.points[0], self._normalize(self._segment_dir(0)))]

        samples = []
        target_distances = [i * spacing for i in range(count)]
        if include_end and not math.isclose(target_distances[-1], length, rel_tol=1e-6):
            target_distances.append(length)

        current_seg = 0
        current_seg_start_dist = 0.0
        for d in target_distances:
            d = min(d, length)
            while current_seg < len(self.points) - 1:
                seg_len = self._dist(self.points[current_seg], self.points[current_seg + 1])
                if current_seg_start_dist + seg_len >= d or math.isclose(current_seg_start_dist + seg_len, d, rel_tol=1e-6):
                    break
                current_seg_start_dist += seg_len
                current_seg += 1

            if current_seg >= len(self.points) - 1:
                samples.append((self.points[-1], self._normalize(self._segment_dir(len(self.points) - 2))))
                continue

            seg_len = self._dist(self.points[current_seg], self.points[current_seg + 1])
            if seg_len <= 0:
                samples.append((self.points[current_seg], self._normalize(self._segment_dir(current_seg))))
                continue

            t = (d - current_seg_start_dist) / seg_len
            t = max(0.0, min(1.0, t))
            a = self.points[current_seg]
            b = self.points[current_seg + 1]
            p = tuple(a[i] + t * (b[i] - a[i]) for i in range(3))
            tangent = self._normalize(self._segment_dir(current_seg))
            samples.append((p, tangent))

        return samples

    def _segment_dir(self, seg_index):
        if seg_index < 0 or seg_index >= len(self.points) - 1:
            return (1.0, 0.0, 0.0)
        a = self.points[seg_index]
        b = self.points[seg_index + 1]
        return tuple(b[i] - a[i] for i in range(3))

    def __repr__(self):
        return f"Route({self.route_type}, {len(self.points)} points, length={self.total_length():.2f})"


class ArcRoute(Route):
    """
    空间圆弧路线。
    默认在 XY 平面（axis='z'），可指定 axis='x' 或 'y'。
    角度单位：度，0° 起算方向按右手定则。
    """

    def __init__(self, center, radius, start_angle, end_angle, axis='z'):
        self.center = tuple(float(v) for v in center)
        self.radius = float(radius)
        self.start_angle = float(start_angle)
        self.end_angle = float(end_angle)
        self.axis = axis.lower()
        self._cached_length = None

    def total_length(self):
        if self._cached_length is None:
            delta = math.radians(abs(self.end_angle - self.start_angle))
            self._cached_length = self.radius * delta
        return self._cached_length

    def _point_at(self, angle_deg):
        theta = math.radians(angle_deg)
        cx, cy, cz = self.center
        r = self.radius
        if self.axis == 'z':
            return (cx + r * math.cos(theta),
                    cy + r * math.sin(theta),
                    cz)
        elif self.axis == 'y':
            return (cx + r * math.cos(theta),
                    cy,
                    cz + r * math.sin(theta))
        elif self.axis == 'x':
            return (cx,
                    cy + r * math.cos(theta),
                    cz + r * math.sin(theta))
        return (cx + r * math.cos(theta),
                cy + r * math.sin(theta),
                cz)

    def _tangent_at(self, angle_deg):
        theta = math.radians(angle_deg)
        # 逆时针切线
        if self.axis == 'z':
            return (-math.sin(theta), math.cos(theta), 0.0)
        elif self.axis == 'y':
            return (-math.sin(theta), 0.0, math.cos(theta))
        elif self.axis == 'x':
            return (0.0, -math.sin(theta), math.cos(theta))
        return (-math.sin(theta), math.cos(theta), 0.0)

    def sample_frames(self, spacing=None, count=None, include_end=True):
        length = self.total_length()
        if length <= 0:
            p = self._point_at(self.start_angle)
            t = self._tangent_at(self.start_angle)
            return [(p, t)]

        if spacing is not None and spacing > 0:
            count = int(length // spacing) + 1
            if include_end and not math.isclose(length % spacing, 0, rel_tol=1e-6):
                count += 1
        elif count is not None and count > 0:
            spacing = length / (count - 1) if count > 1 else 0
        else:
            spacing = length
            count = 2

        if count == 1:
            p = self._point_at(self.start_angle)
            t = self._tangent_at(self.start_angle)
            return [(p, t)]

        samples = []
        delta = self.end_angle - self.start_angle
        for i in range(count):
            ratio = i / (count - 1)
            angle = self.start_angle + ratio * delta
            samples.append((self._point_at(angle), self._normalize(self._tangent_at(angle))))
        return samples

    def sample_points(self, spacing=None, count=None, include_end=True):
        return [p for p, _ in self.sample_frames(spacing=spacing, count=count, include_end=include_end)]

    def __repr__(self):
        return (f"ArcRoute(center={self.center}, r={self.radius}, "
                f"angles=({self.start_angle},{self.end_angle}), axis={self.axis})")


def generate_linear_route(start, end):
    """生成直线路线"""
    return Route.line(start, end)


def sample_route_for_components(route, spacing=None, count=None, include_end=True):
    """沿路线采样布置点"""
    return route.sample_points(spacing=spacing, count=count, include_end=include_end)
