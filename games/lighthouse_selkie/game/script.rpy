# The script of the game goes in this file.

# Declare characters used by this game. The color argument colorizes the
# name of the character.

define e = Character("Eileen")
image bg lighthouse storm = "images/bg_lighthouse_storm.png"
image selkie neutral = "images/selkie_neutral.png"
define keeper = Character("Ewan", color="#335577")
define selkie = Character("???", color="#88aacc")


# The game starts here.

label start:

    # Show a background. This uses a placeholder by default, but you can
    # add a file (named either "bg room.png" or "bg room.jpg") to the
    # images directory to show it.

    scene bg lighthouse storm

    # This shows a character sprite. A placeholder is used, but you can
    # replace it by adding a file named "eileen happy.png" to the images
    # directory.

    show selkie neutral

    # These display lines of dialogue.

    e "You've created a new Ren'Py game."

    e "Once you add a story, pictures, and music, you can release it to the world!"

    # This ends the game.

    jump opening

label opening:
    scene bg lighthouse storm
    keeper "Another storm rolling in off the Atlantic. Third one this week."
    keeper "The lamp needs tending, the log needs writing... and I need sleep that won't come."
    keeper "Still, there's something out on the rocks tonight. Something that weren't there yesterday."
    keeper "Best go have a look before the tide comes up."
    jump meeting

label meeting:
    scene bg lighthouse storm
    show selkie neutral
    keeper "Hello? Is someone out there? These rocks are treacherous in a storm!"
    selkie "You tend the light, yes? The one that guides the lost ones home."
    keeper "Aye... have done for fifteen years. Who are you? You shouldn't be out here without shoes."
    selkie "I am older than your lighthouse, keeper. And I have watched your light for every one of those years."
    return
