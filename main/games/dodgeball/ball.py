import math
import random

import pygame

from main import styles
from . import sketches
from .collision import build_body, point_in_polygon, point_segment_distance, swept_circle_hits

ORANGE = styles.DODGEBALL.ball_medium

class Ball:
  """Ball that bounces around the screen randomly."""

  def __init__(
      self,
      x: float,
      y: float,
      radius: float = 25,
      max_speed: float = 40.0,
      elasticity: float = 0.95,
      color: tuple[int, int, int] | None = None,
  ):
      self.x = x
      self.y = y
      # Where the ball was before the last move: collisions sweep prev -> current.
      self.prev_x = x
      self.prev_y = y
      self.radius = radius
      self.max_speed = max_speed
      self.elasticity = elasticity
      self.vx = 0.0
      self.vy = 0.0
      self.reset_velocity()
      self.color = color if color is not None else ORANGE
      self.pace = "medium"  # "slow" | "medium" | "fast": picks the sketch colour
      self.spin = 0.0  # degrees; the seams turn as the ball travels
  
  def reset_velocity(self) -> None:
      """Give the ball a random initial velocity."""
      angle = random.uniform(0, 2 * math.pi)
      speed = random.uniform(10, self.max_speed)
      self.vx = math.cos(angle) * speed
      self.vy = math.sin(angle) * speed
  
  def move(self) -> None:
      """Update ball position."""
      self.prev_x, self.prev_y = self.x, self.y
      self.x += self.vx
      self.y += self.vy
      # Spin with travel, in the direction it's heading sideways (kept slow so it
      # never strobes at top speed).
      travel = math.hypot(self.vx, self.vy)
      self.spin = (self.spin - math.copysign(1.0, self.vx or 1.0) * math.degrees(travel / max(1.0, self.radius)) * 0.2) % 360
      
      # Clamp speed
      speed = math.sqrt(self.vx**2 + self.vy**2)
      if speed > self.max_speed:
          scale = self.max_speed / speed
          self.vx *= scale
          self.vy *= scale
  
  def bounce(self, width: float, height: float) -> bool:
      """Bounce off screen boundaries with randomness. True if it hit a wall."""
      hit_wall = (
          self.x - self.radius < 0
          or self.x + self.radius > width
          or self.y - self.radius < 0
          or self.y + self.radius > height
      )
      if self.x - self.radius < 0:
          self.x = self.radius
          self.vx = -self.vx * self.elasticity
          self.vy += random.uniform(-3, 3)
          if random.random() < 0.1:
              self.vy = random.uniform(-10, 10)
      elif self.x + self.radius > width:
          self.x = width - self.radius
          self.vx = -self.vx * self.elasticity
          self.vy += random.uniform(-3, 3)
          if random.random() < 0.1:
              self.vy = random.uniform(-10, 10)
      
      if self.y - self.radius < 0:
          self.y = self.radius
          self.vy = -self.vy * self.elasticity
          self.vx += random.uniform(-3, 3)
          if random.random() < 0.1:
              self.vx = random.uniform(-10, 10)
      elif self.y + self.radius > height:
          self.y = height - self.radius
          self.vy = -self.vy * self.elasticity
          self.vx += random.uniform(-3, 3)
          if random.random() < 0.1:
              self.vx = random.uniform(-10, 10)
      
      # Random direction change (1% chance)
      if random.random() < 0.01:
          angle_change = random.uniform(-math.pi/4, math.pi/4)
          current_angle = math.atan2(self.vy, self.vx)
          new_angle = current_angle + angle_change
          speed = math.sqrt(self.vx**2 + self.vy**2)
          self.vx = math.cos(new_angle) * speed
          self.vy = math.sin(new_angle) * speed
      return hit_wall
  
  def check_collision(self, person) -> tuple[bool, list | None]:
      """Does the ball touch this person's body (head, torso, limbs)?

      Uses only confident keypoints and sweeps the ball from last frame's
      position, so a fast ball cannot pass through a thin limb between frames.

      Returns:
          (collision, body points): the confident keypoints, whose centre the
          game uses to bounce the ball away; None when nobody was given.
      """
      if person is None:
          return False, None
      body = build_body(person.xy, getattr(person, "conf", None), tuple(person.box))
      hit = swept_circle_hits((self.prev_x, self.prev_y), (self.x, self.y), self.radius, body)
      return hit, list(body.points)

  def _point_in_polygon(self, point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
      """Check if a point is inside a polygon (even-odd ray cast)."""
      return point_in_polygon(point, polygon)

  def _point_to_line_distance(
      self,
      point: tuple[float, float],
      line_p1: tuple[float, float],
      line_p2: tuple[float, float],
  ) -> float:
      """Distance from a point to a line segment (safe when both ends coincide)."""
      return point_segment_distance(point, line_p1, line_p2)

  def draw(self, canvas: pygame.Surface) -> None:
      """Draw the hand-drawn ball for its current pace, with speed lines when quick."""
      size = int(self.radius) * 2 + 16  # room for the marker outline around the ball
      sketches.draw_ball(canvas, (self.x, self.y), size, self.pace, self.spin, (self.vx, self.vy))
