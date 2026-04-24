## script.rpy — entry point for the fixture VN.
##
## Two characters, a branching menu, an image alias, and an audio play.
## Deliberately small but exercises every read-tool path.

define e = Character("Eileen", color="#0099cc")
define m = Character("Mei", color="#cc6699")

image bg park = "images/park.png"
image bg cafe = "images/cafe.png"

default met_mei = False
default affection_mei = 0

label start:
    scene bg park
    play music "audio/spring_theme.ogg" fadein 1.0

    e "Welcome to the tiny fixture project."
    e "It's small on purpose — easy to scan, easy to mutate."

    menu:
        "Visit the cafe":
            $ met_mei = True
            jump cafe_scene

        "Stay in the park":
            jump park_scene

label cafe_scene:
    scene bg cafe
    m "Hi! I'm Mei. Nice to meet you."
    $ affection_mei += 1
    jump ending

label park_scene:
    e "The park is quiet today."
    jump ending

label ending:
    if met_mei:
        e "You met someone new today."
    else:
        e "A peaceful day on your own."
    return
