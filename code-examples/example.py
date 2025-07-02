import pygame

# initialize pygame
pygame.init()

# screen settings
WIDTH, HEIGHT = 900, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

# player settings
player = pygame.Rect(100, 550, 50, 50)
velocity_x, velocity_y = 0, 0
ground_y = HEIGHT  # bottom of the screen
gravitational_force = 0.5
drag = 0.9
jump_strength = -9
jumpsLeft = 100

# game loop
running = True
while running:
    screen.fill((0, 0, 0))  # clear screen
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    keys = pygame.key.get_pressed()
    if keys[pygame.K_w] and jumpsLeft:
        velocity_y = jump_strength
        jumpsLeft -= 1
    if keys[pygame.K_d]:
        velocity_x = 5
    if keys[pygame.K_a]:
        velocity_x = -5
    if keys[pygame.K_SPACE] and jumpsLeft:
        velocity_y = jump_strength
        jumpsLeft -= 1
    
    # apply gravity
    velocity_y += gravitational_force
    
    # apply drag
    velocity_x *= drag
    
    # update position
    player.x += velocity_x
    player.y += velocity_y
    
    # ground collision
    if player.y + player.height >= ground_y:
        player.y = ground_y - player.height
        velocity_y = 0
        jumpsLeft = 100
    
    # draw player
    pygame.draw.rect(screen, (255, 0, 0), player)
    
    jump_strength = -jumpsLeft/10
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
