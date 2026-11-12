import math
import random

import pygame

from main import styles
from main.settings import ASSETS

ORANGE = styles.DODGEBALL.ball_medium

# Sprite per pace (set by the game from the ball's speed each frame).
_SPRITES = {
    "slow": ASSETS / "sprites" / "slow.png",
    "medium": ASSETS / "sprites" / "medium.png",
    "fast": ASSETS / "sprites" / "fast.png",
}
_sprite_cache: dict[tuple[str, int], pygame.Surface] = {}


def _sprite(pace: str, size: int) -> pygame.Surface:
    key = (pace, size)
    if key not in _sprite_cache:
        img = pygame.image.load(str(_SPRITES[pace]))
        if pygame.display.get_surface() is not None:
            img = img.convert_alpha()
        _sprite_cache[key] = pygame.transform.smoothscale(img, (size, size))
    return _sprite_cache[key]


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
      self.radius = radius
      self.max_speed = max_speed
      self.elasticity = elasticity
      self.vx = 0.0
      self.vy = 0.0
      self.reset_velocity()
      self.color = color if color is not None else ORANGE
      self.pace = "medium"  # "slow" | "medium" | "fast": picks the sprite
  
  def reset_velocity(self) -> None:
      """Give the ball a random initial velocity."""
      angle = random.uniform(0, 2 * math.pi)
      speed = random.uniform(10, self.max_speed)
      self.vx = math.cos(angle) * speed
      self.vy = math.sin(angle) * speed
  
  def move(self) -> None:
      """Update ball position."""
      self.x += self.vx
      self.y += self.vy
      
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
      """Check if ball collides with person's body shape (keypoints polygon).
      
      Returns:
          Tuple of (collision: bool, body_polygon_points: list | None)
      """
      if person is None:
          return False, None
      
      # Get all keypoints from the person
      keypoints = person.xy
      
      # Create a polygon from the keypoints for more accurate collision
      # Use all 17 COCO keypoints to form the body shape
      body_polygon = []
      for i in range(len(keypoints)):
          x, y = float(keypoints[i, 0]), float(keypoints[i, 1])
          body_polygon.append((x, y))
      
      # Check if ball center is inside the polygon
      if self._point_in_polygon((self.x, self.y), body_polygon):
          return True, body_polygon
      
      # Also check if ball is close to any edge of the polygon
      # This gives a little buffer space
      for i in range(len(body_polygon)):
          p1 = body_polygon[i]
          p2 = body_polygon[(i + 1) % len(body_polygon)]
          if self._point_to_line_distance((self.x, self.y), p1, p2) < self.radius:
              return True, body_polygon
      
      return False, body_polygon
  
  def _point_in_polygon(self, point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
      """Check if a point is inside a polygon using ray casting algorithm."""
      x, y = point
      n = len(polygon)
      inside = False
      p1x, p1y = polygon[0]
      for i in range(n + 1):
          p2x, p2y = polygon[i % n]
          if y > min(p1y, p2y):
              if y <= max(p1y, p2y):
                  if x <= max(p1x, p2x):
                      if p1y != p2y:
                          xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                      if p1x == p2x or x <= xinters:
                          inside = not inside
          p1x, p1y = p2x, p2y
      return inside
  
  def _point_to_line_distance(self, point: tuple[float, float], line_p1: tuple[float, float], line_p2: tuple[float, float]) -> float:
      """Calculate distance from point to line segment."""
      x, y = point
      x1, y1 = line_p1
      x2, y2 = line_p2
      
      # Calculate the line equation: ax + by + c = 0
      a = y2 - y1
      b = x1 - x2
      c = x2 * y1 - x1 * y2
      
      # Distance from point to infinite line
      distance = abs(a * x + b * y + c) / math.sqrt(a * a + b * b)
      
      # Check if the closest point on the line is within the segment
      # Project point onto line
      dot = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / ((x2 - x1) ** 2 + (y2 - y1) ** 2)
      
      if dot < 0:
          # Closest to p1
          return math.sqrt((x - x1) ** 2 + (y - y1) ** 2)
      elif dot > 1:
          # Closest to p2
          return math.sqrt((x - x2) ** 2 + (y - y2) ** 2)
      else:
          # Closest to line segment
          return distance
  
  def draw(self, canvas: pygame.Surface) -> None:
      """Draw the ball as the sprite for its current pace."""
      sprite = _sprite(self.pace, int(self.radius) * 2 + 8)
      canvas.blit(sprite, sprite.get_rect(center=(int(self.x), int(self.y))))
