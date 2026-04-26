image bg office night = "images/bg_office_night.png"
image detective neutral = "images/detective_neutral.png"
define det = Character("Det. Vance", color="#445566")
# Entry point. The `start` label runs first when the player clicks
# "New Game". Body is intentionally empty — fill it via
# add_dialogue_block(label="start", lines=[...]) or point start at
# your real opening with set_start_target(target="<label>").

label start:
    jump opening

label opening:
    scene bg office night
    det "Three nights running, and still no leads."
    det "The rain doesn't care about my deadline."
    det "Neither does whoever put that body on the docks."
    return
