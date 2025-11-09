Py-Boom

Py-Boom is a fast-paced, 1-bit-style arcade game written in
CircuitPython for the Adafruit Fruit Jam and other compatible
display boards.

This game is a modern take on a classic "catcher" formula,
featuring both a single-player mode against an AI and a
competitive two-player versus mode.

Game Modes

At the title screen, you can select your game mode:

1-Player Mode:
You control the Bucket (P1) at the bottom of the screen.
An AI-controlled Bomber moves at the top, dropping bombs at
an increasing rate. Your goal is to catch as many bombs as
possible to survive the level.

2-Player Mode:
Player 1 controls the Bucket, and Player 2 controls the
Bomber. P1's goal is to survive, while P2's goal is to
drop bombs strategically to make P1 miss.

How to Play

P1 (Bucket) - The Catcher

Goal:
Catch every bomb that is dropped. If you miss a bomb, you
lose one of your buckets (lives). If you lose all three,
the game is over.

Winning:
If you (P1) successfully catch all bombs in a level (e.g.,
10 bombs in Level 1), you win the round and advance to the
next, more difficult level.

P2 (Bomber) - The Attacker

Goal:
Make P1 miss! You have a limited number of bombs per level.
Use your movement and timing to drop bombs where P1 isn't.

Winning:
If you (P2) successfully make P1 lose all three of their
buckets, you win the game!

Controls

Action:         Player 1 (Bucket):    Player 2 (Bomber):
Move Left       'A' key               'Left Arrow' key
Move Right      'D' key               'Right Arrow' key
Drop Bomb       N/A                   'Down Arrow' key
Start / Ready   'Space' bar           'Enter' key

Other Controls

Select Mode:
On the title screen, press the '1' or '2' key.

Restart Game:
On the "Game Over" screen, press the 'R' key to return to
the title screen.

Required Files

To run this game, you will need the following files on your
CircuitPython device:

code.py:
The main game code.

pyboom.bmp:
The title screen logo.

bomb_icon.bmp:
The bomb sprite icon (used in development).

This project was started in Microsoft MakeCode Arcade. I then moved the Python to Visual Studio Code and started converting Circuit Python. I used the different AI tools in VS Code to help with the translations. As I ran out of tokens in VS Code I moved to Gemini where I have more tokens and worked through the different versions there. I will try to put all of my Gemini prompts as I have time in the AI Prompts folder.
