image bg lighthouse = "images/bg_lighthouse.png"
image visitor neutral = "images/visitor_neutral.png"
define keeper = Character("Ewan", color="#5588aa")
define visitor = Character("???", color="#aa88cc")
# Entry point. The `start` label runs first when the player clicks
# "New Game". Body is intentionally empty — fill it via
# add_dialogue_block(label="start", lines=[...]) or point start at
# your real opening with set_start_target(target="<label>").

label start:
    jump opening

label opening:
    scene bg lighthouse
    show visitor neutral
    keeper "Another storm rolling in. The sea doesn't rest tonight."
    visitor "Neither do I, keeper. I've walked a long road to find this light."
    keeper "Who are you? No boat could survive those waves..."
    return
