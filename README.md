<!-- Docs -->

## How it Works (Flow)

```
EPISODE START:

1. env.reset()
    |--- Initialize grid, robot at (0,0), place packages
    |--- Return initial observation

2. Agent sees Observation 
    |--- Robot at (0,0), packages at (2,2) and (4,4)

3. Agent decides action
    |--- RobotAction(direction="right", action="move")

4. env.step(action)
    |--- Update robot position (0,0) → (1,0)
    |--- Check if at package location -> No 
    |--- Update time (deadline countdown)
    |--- Calculate reward -> -0.01 (Just moved, wasted time)
    |--- Check if done -> No
    |--- Return: Observation, reward (-0.01), done (False), info

5. Agent learns 
    |--- That move got -0.01, not good

6. Repeat step 3-5 until done

EPISODE END:

When done=True:
  |--- All packages delivered OR max steps reached
  |--- Calculate total score
  |--- env.reset() for next episode

```


## REWARD STRUCTURE (Scoring)

```
REWARD SYSTEM:

+1.0   = Package delivered successfully
+0.2   = Moved closer to target package
-0.01  = Each step (efficiency penalty, hurry!)
-0.5   = Missed package deadline
-0.2   = Delivered wrong package to destination
-0.5   = Invalid action (moved into boundary)
0.0    = No-op action

"Agent learns:"
    "Delivery = BIG +1.0"
    "Each step = small -0.01"
    "Missing deadline = BIG -0.5"
    "Therefore: Hurry, pick urgent packages first"
```

## Task Configuration (3 Levels)

```
EASY TASK (LEVEL 1):
    Grid Size: 5x5
    Robot: (0,0)
    Packages: 2 packages 
        - Package A at (2,2), deadline 15
        - Package B at (3,3), deadline 15
    Obstacles: NONE
    Max Steps: 20
    Difficulty: Simple
    What agent learns: Just pick and dilever

    Expected Score: ~0.4-0.6 (random agent sometimes succeeds)

---- meaning of random agent?:
        actions = ["up", "down", "left", "right", "pick", "deliver"]
        action = random.choice(actions)

-----how that score is calc?:
        Best case - Delivered both packages 
        score 2/2 = 1.0 (delivered on time/ total_package)

        partial Success 
        score 1/2 = 0.5

        Failed 
        score 0/2 = 0

MEDIUM TASK (LEVEL 2):
    Grid Size: 10x10
        Robot: (0,0)
        Packages: 4 packages 
            - Package A at (2, 2), deadline 10
            - Package B at (8, 8), deadline 8
            - Package C at (5, 5), deadline 12
            - Package D at (3, 7), deadline 7``
        Obstacles: 5 Walls
        Max Steps: 50
        Difficulty: Moderate
        What agent learns: Pick urgent packages first

        Expected Score: ~0.2-0.4 (random agent rarely succeeds)


HARD TASK (LEVEL 3):
    Grid Size: 15x15
    Robot: (0, 0)
    Packages: 6 packages
        - Package A at (2, 2), deadline 8
        - Package B at (14, 14), deadline 5
        - Package C at (7, 7), deadline 10
        - Package D at (3, 10), deadline 6
        - Package E at (11, 3), deadline 9
        - Package F at (9, 11), deadline 7
    Obstacles: 15 walls (maze-like)
    Max Steps: 100
    Difficulty: Complex
    What agent learns: "Optimize complex priorities"
    
    Expected Score: ~0.05-0.15 (random agent almost never succeeds)

```