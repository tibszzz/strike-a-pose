"""Dodgeball Game: Avoid the bouncing ball! Hit = lose points."""

from __future__ import annotations

import math
import random

import pygame

from strike_a_pose.pose import PoseFrame

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (80, 170, 255)
RED = (255, 80, 80)
GREEN = (100, 255, 100)
YELLOW = (255, 255, 100)
ORANGE = (255, 165, 0)


class Ball:
    """Ball that bounces around the screen randomly."""
    
    def __init__(
        self,
        x: float,
        y: float,
        radius: float = 50,     # Ball radius in pixels
        max_speed: float = 40.0, # Maximum speed in pixels per frame
        elasticity: float = 0.95, # Elasticity factor for bouncing (0-1)
    ):
        self.x = x
        self.y = y
        self.radius = radius
        self.max_speed = max_speed
        self.elasticity = elasticity
        self.vx = 0.0
        self.vy = 0.0
        self.reset_velocity()
        self.color = ORANGE
    
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
    
    def bounce(self, width: float, height: float) -> None:
        """Bounce off screen boundaries with randomness."""
        if self.x - self.radius < 0:
            self.x = self.radius
            self.vx = -self.vx * self.elasticity
            # Add randomness
            self.vy += random.uniform(-3, 3)
            # Occasionally add energy
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
    
    def check_collision(self, person, draw_box: bool = False) -> tuple[bool, pygame.Rect | None]:
        """Check if ball collides with person's body bounding box.
        
        Returns:
            Tuple of (collision: bool, box_rect: pygame.Rect | None)
        """
        if person is None:
            return False, None
        
        x1, y1, x2, y2 = person.box
        box_rect = pygame.Rect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))
        
        # Find closest point on the box to the ball
        closest_x = max(x1, min(self.x, x2))
        closest_y = max(y1, min(self.y, y2))
        
        # Distance from ball center to closest point on box
        dx = self.x - closest_x
        dy = self.y - closest_y
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Collision if distance < ball radius
        return distance < self.radius, box_rect
    
    def draw(self, canvas: pygame.Surface) -> None:
        """Draw the ball."""
        # Glow effect
        pygame.draw.circle(canvas, self.color, (int(self.x), int(self.y)), int(self.radius) + 4, 2)
        # Filled ball
        pygame.draw.circle(canvas, self.color, (int(self.x), int(self.y)), int(self.radius))
        # Highlight
        pygame.draw.circle(canvas, WHITE, (int(self.x) - 5, int(self.y) - 5), 4)


class DodgeballGame:
    title = "Dodgeball"

    def __init__(self, size):
        self.w, self.h = size
        
        # Ball
        self.ball = Ball(
            x=self.w // 2,
            y=self.h // 2,
            radius=50,
            max_speed=40.0,
            elasticity=0.95,
        )
        
        # Score
        self.score = 0
        self.hits = 0
        
        # Visual effects
        self.hit_timer = 0
        self.hit_position = (0, 0)
    
    def reset(self) -> None:
        """Reset the game."""
        self.ball = Ball(
            x=self.w // 2,
            y=self.h // 2,
            radius=50,
            max_speed=40.0,
            elasticity=0.95,
        )
        self.score = 0
        self.hits = 0
        self.hit_timer = 0
        self.person_boxes = []

    def update(self, frame: PoseFrame) -> None:
        """Update game state."""
        # Store person boxes for drawing
        self.person_boxes = []
        
        # Move ball
        self.ball.move()
        self.ball.bounce(self.w, self.h)
        
        # Update hit timer
        if self.hit_timer > 0:
            self.hit_timer -= 1
        
        # Check for collisions
        for person in frame.players:
            if person is not None:
                collision, box_rect = self.ball.check_collision(person)
                self.person_boxes.append((person, box_rect))
                
                if collision:
                    # Hit!
                    self.hits += 1
                    self.score -= 1
                    self.hit_timer = 45
                    self.hit_position = (int(self.ball.x), int(self.ball.y))
                    
                    # Bounce ball away from person
                    x1, y1, x2, y2 = person.box
                    box_center_x = (x1 + x2) / 2
                    box_center_y = (y1 + y2) / 2
                    
                    # Calculate direction from person center to ball
                    dx = self.ball.x - box_center_x
                    dy = self.ball.y - box_center_y
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    # If ball is very close or inside the box, push it out
                    if dist < 1:
                        # Ball is at the center, push in a random direction
                        angle = random.uniform(0, 2 * math.pi)
                        self.ball.vx = math.cos(angle) * 15
                        self.ball.vy = math.sin(angle) * 15
                        # Move ball outside the box
                        self.ball.x = box_center_x + math.cos(angle) * (self.ball.radius + 30)
                        self.ball.y = box_center_y + math.sin(angle) * (self.ball.radius + 30)
                    else:
                        # Push ball away in the opposite direction
                        self.ball.vx = (dx / dist) * 15
                        self.ball.vy = (dy / dist) * 15
                        # Ensure ball is outside the box
                        push_dist = self.ball.radius + 30
                        self.ball.x = box_center_x + (dx / dist) * push_dist
                        self.ball.y = box_center_y + (dy / dist) * push_dist
                    
                    break  # Only check first person
        
        else:
            # No collision - increment score slowly
            if self.hits == 0:
                self.score += 0.01
        
        # Update ball color based on speed
        speed = math.sqrt(self.ball.vx**2 + self.ball.vy**2)
        if speed > 15:
            self.ball.color = RED
        elif speed > 8:
            self.ball.color = ORANGE
        else:
            self.ball.color = YELLOW

    def render_camera(self, image_bgr):
        """Pass through camera image."""
        return image_bgr

    def debug_lines(self) -> list[str]:
        return [
            f"Score: {self.score:.0f} | Hits: {self.hits}",
            f"Ball speed: {math.sqrt(self.ball.vx**2 + self.ball.vy**2):.1f} px/f",
        ]

    def draw(self, canvas: pygame.Surface, frame: PoseFrame) -> None:
        """Draw game elements."""
        # Draw person bounding boxes
        for person, box_rect in self.person_boxes:
            if box_rect is not None:
                # Draw transparent rectangle around person
                temp_surf = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
                pygame.draw.rect(temp_surf, (*BLUE, 80), box_rect, 3)
                canvas.blit(temp_surf, (0, 0))
        
        # Draw ball
        self.ball.draw(canvas)
        
        # Draw hit effect
        if self.hit_timer > 0:
            alpha = int(255 * (self.hit_timer / 45))
            temp_surf = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
            radius = int(30 + (45 - self.hit_timer))
            pygame.draw.circle(temp_surf, (*RED, alpha), self.hit_position, radius, 3)
            
            # X mark
            x, y = self.hit_position
            pygame.draw.line(temp_surf, (*RED, alpha),
                            (x - 25, y - 25), (x + 25, y + 25), 3)
            pygame.draw.line(temp_surf, (*RED, alpha),
                            (x - 25, y + 25), (x + 25, y - 25), 3)
            canvas.blit(temp_surf, (0, 0))
        
        # Draw score at bottom
        font = pygame.font.SysFont("menlo,monaco,courier", 28)
        score_color = RED if self.score < 0 else GREEN
        score_text = font.render(f"Score: {int(self.score)}", True, score_color, BLACK)
        canvas.blit(score_text, (20, self.h - 40))
