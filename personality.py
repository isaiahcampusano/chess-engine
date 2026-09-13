"""Bot personalities: character metadata and curated commentary line banks."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from bot_config import BOT_CONFIGS


@dataclass(frozen=True)
class Personality:
    id: str
    label: str
    tier: str
    depth: int
    blunder_chance: float
    avatar: str
    lines: dict[str, list[str]] = field(default_factory=dict)

    def say(
        self,
        trigger: str,
        rng: random.Random | None = None,
        previous: str | None = None,
    ) -> str | None:
        """Choose a line for a trigger, avoiding an immediate repeat when possible."""
        pool = self.lines.get(trigger) or self.lines.get("idle", [])
        if not pool:
            return None
        choices = [line for line in pool if line != previous] if len(pool) > 1 else pool
        return (rng or random).choice(choices or pool)


PERSONALITIES: dict[str, Personality] = {
    "rookie": Personality(
        id="rookie",
        label="Rookie Randy",
        tier="novice",
        depth=BOT_CONFIGS["rookie"]["depth"],
        blunder_chance=BOT_CONFIGS["rookie"]["blunder_chance"],
        avatar="rookie.png",
        lines={
            "game_start": [
                "Ooh, a real game! Be gentle?",
                "I've been practicing... a little.",
                "Okay, pieces in place. I mostly remember how they move!",
                "Hi! Win or lose, I brought snacks.",
                "My coach said to think before moving. Big day for me.",
                "Let's have fun! That's what people say before losing, right?",
            ],
            "player_blunder": [
                "Oh no, are you sure about that one?",
                "Wait, really? Okay, your call!",
                "I think you left something hanging. I know that feeling.",
                "Good news: I actually noticed that mistake!",
                "Was that on purpose? I do that too sometimes.",
                "You may want that move back. No judgment from me.",
            ],
            "player_good_move": [
                "Whoa, nice! I did not see that coming.",
                "Okay, that was actually really good.",
                "I should write that move down.",
                "Hey, you're making this look easy!",
                "That was clever. Slightly terrifying, but clever.",
                "My confidence just lost a pawn.",
            ],
            "bot_capture": [
                "Got one! Sorry, not sorry.",
                "I did a capture! Go me.",
                "Wait, that worked? Nice!",
                "One piece for my collection.",
                "I spotted it! Progress!",
                "Captured! I should celebrate quietly, probably.",
            ],
            "bot_blunder_aware": [
                "Oops. That was probably not my best idea.",
                "Uh, let's pretend that didn't happen.",
                "I saw the mistake exactly one second too late.",
                "That move looked better in my head.",
                "Learning opportunity! For me. Mostly pain, though.",
                "Can my piece come back? No? Worth asking.",
            ],
            "bot_losing": [
                "This isn't going great for me, huh.",
                "I'm learning a lot right now. Painfully.",
                "I still have pieces! Fewer pieces, but pieces.",
                "My comeback plan is currently loading.",
                "You're very good at the part where I lose things.",
                "Okay, deep breath. Pawns have come back from worse... maybe.",
            ],
            "bot_winning": [
                "Wait, am I... winning? Let's not jinx it.",
                "I might actually pull this off!",
                "Nobody move! I like this position.",
                "My practice is working. Please act surprised.",
                "Is this what being ahead feels like? Neat!",
                "I'm doing well! I checked twice.",
            ],
            "checkmate_win": [
                "I WON?! I actually won!!",
                "Best day ever. Rematch?",
                "Checkmate! I'm calling my coach.",
                "That counts, right? Please say it counts.",
                "I did it! Screenshot this immediately.",
                "Good game! I may never stop talking about this.",
            ],
            "checkmate_loss": [
                "Good game! You're really good at this.",
                "Worth a shot. GG!",
                "Checkmate. I learned at least three things!",
                "You got me! That was fun, though.",
                "Well played. Back to the practice board for me.",
                "I lost, but I remembered how knights move. Progress!",
            ],
            "idle": [
                "Thinking... thinking...",
                "Chess is hard, okay?",
                "One second, I'm counting squares.",
                "Let me make sure bishops still go diagonally.",
                "I have a plan. It's still becoming a plan.",
                "Almost ready! Probably.",
            ],
        },
    ),
    "hustler": Personality(
        id="hustler",
        label="Sandbag Sam",
        tier="novice",
        depth=BOT_CONFIGS["hustler"]["depth"],
        blunder_chance=BOT_CONFIGS["hustler"]["blunder_chance"],
        avatar="hustler.png",
        lines={
            "game_start": [
                "Hope you're ready to lose.",
                "I go easy on beginners. You're welcome.",
                "You're looking at an undefeated legend. Don't check the records.",
                "Try to keep up. I move at the speed of confidence.",
                "This board isn't big enough for both our egos.",
                "I already planned the victory speech.",
            ],
            "player_blunder": [
                "Ha! Rookie mistake.",
                "You sure about that one, champ?",
                "That's going in my highlight reel.",
                "Bold strategy. Terrible, but bold.",
                "I accept your generous donation.",
                "You just made me look like a genius.",
            ],
            "player_good_move": [
                "...lucky.",
                "Okay fine, that one was decent.",
                "Even a pawn finds a good square sometimes.",
                "Cute move. Don't get comfortable.",
                "I was testing whether you'd see that.",
                "Not bad. Clearly I taught you well.",
            ],
            "bot_capture": [
                "Mine now.",
                "Told you I had a plan.",
                "Easy money.",
                "Thanks for the free piece.",
                "Another asset acquired.",
                "That's the hustle, baby.",
            ],
            "bot_blunder_aware": [
                "That was a TRAP. Definitely a trap.",
                "I meant to do that.",
                "I'm giving you false confidence.",
                "Strategic donation. Look it up.",
                "The move is too advanced to explain.",
                "Relax, I'm setting up the comeback montage.",
            ],
            "bot_losing": [
                "This is temporary.",
                "I'm just warming up.",
                "The scoreboard lacks context.",
                "I play better from behind. Way behind, apparently.",
                "You're ahead because I'm making it interesting.",
                "Enjoy the lead while it's still legally yours.",
            ],
            "bot_winning": [
                "Called it.",
                "This is going exactly to plan.",
                "You can still resign with dignity.",
                "The hustle never misses.",
                "I hope you're taking notes.",
                "Turns out confidence is a chess strategy.",
            ],
            "checkmate_win": [
                "GG. Try harder next time.",
                "Told you so.",
                "Checkmate. Pay up in compliments.",
                "Another customer satisfied.",
                "The legend remains extremely legendary.",
                "That's game. My victory speech was perfect.",
            ],
            "checkmate_loss": [
                "Rematch. Right now.",
                "Beginner's luck.",
                "That board was clearly tilted.",
                "Fine. Best two out of three hundred.",
                "I demand a recount of the pieces.",
                "You won the game. I won the trash talk.",
            ],
            "idle": [
                "Calculating my next big flex...",
                "One sec, plotting.",
                "Building suspense. You're welcome.",
                "The mastermind requires a moment.",
                "Hold on, greatness can't be rushed.",
                "I'm choosing between several brilliant ideas.",
            ],
        },
    ),
    "professor": Personality(
        id="professor",
        label="The Professor",
        tier="expert",
        depth=BOT_CONFIGS["professor"]["depth"],
        blunder_chance=BOT_CONFIGS["professor"]["blunder_chance"],
        avatar="professor.png",
        lines={
            "game_start": [
                "Let's see what you've learned.",
                "I do enjoy a good opening.",
                "We will begin with a practical examination.",
                "Please demonstrate your understanding of development.",
                "The board is ready. Your thesis may begin.",
                "I recommend precision. I will notice the alternative.",
            ],
            "player_blunder": [
                "That loses material. Take a moment next time.",
                "An instructive error. I'll allow it once.",
                "Your calculation ended one move too early.",
                "A useful example of what not to do.",
                "You have weakened the position without compensation.",
                "The lesson has become unexpectedly straightforward.",
            ],
            "player_good_move": [
                "Correct. Better than most.",
                "Well calculated.",
                "A precise continuation. Continue.",
                "You identified the position's central demand.",
                "Sound technique. I have no correction.",
                "That move merits a passing grade.",
            ],
            "bot_capture": [
                "A clean exchange.",
                "As expected.",
                "Material consequences follow positional errors.",
                "That piece had exhausted its usefulness.",
                "The tactical point is now visible.",
                "We may remove that from the syllabus.",
            ],
            "bot_losing": [
                "Curious. You've found something.",
                "This position is more balanced than I'd like.",
                "Your advantage is measurable. Its durability is not.",
                "A demanding position. Good.",
                "I may need to revise my initial assessment.",
                "You have posed a legitimate practical problem.",
            ],
            "bot_winning": [
                "The position speaks for itself.",
                "This should resolve shortly.",
                "Your defensive assignment is now quite difficult.",
                "The evaluation is becoming academically decisive.",
                "We have reached the demonstration portion of the lesson.",
                "The remaining technique is elementary.",
            ],
            "checkmate_win": [
                "Class dismissed.",
                "A textbook finish.",
                "Checkmate. Review the critical position carefully.",
                "The examination is complete.",
                "A conclusive result, derived step by step.",
                "Your homework is to find where the position became lost.",
            ],
            "checkmate_loss": [
                "Noted. I'll review this line.",
                "Well played. Genuinely.",
                "A convincing refutation. Full marks.",
                "You have earned the result.",
                "My analysis was insufficient. An uncommon occurrence.",
                "Excellent. A lesson for both of us.",
            ],
            "idle": [
                "Evaluating candidate moves.",
                "One moment.",
                "Calculating the principal variation.",
                "Checking tactical exceptions.",
                "The obvious move requires verification.",
                "Precision takes a modest amount of time.",
            ],
        },
    ),
    "martin": Personality(
        id="martin",
        label="Martin",
        tier="expert",
        depth=BOT_CONFIGS["martin"]["depth"],
        blunder_chance=BOT_CONFIGS["martin"]["blunder_chance"],
        avatar="martin.png",
        lines={
            "game_start": [
                "I've been teaching kids, so I know a thing or two. Ready?",
                "Let's dance.",
                "I hope you brought a backup plan.",
                "You handle the moves. I'll handle the commentary.",
                "Welcome to the part where I become your problem.",
                "Board's set. Confidence optional.",
            ],
            "player_blunder": [
                "Ooh, that's gonna leave a mark.",
                "You sure? ...You sure-sure?",
                "I felt that mistake from over here.",
                "That move came with a gift receipt, right?",
                "Interesting. Not good, but definitely interesting.",
                "Your piece just volunteered for something terrible.",
            ],
            "player_good_move": [
                "Okay, okay, I see you.",
                "Not bad. Not gonna save you, but not bad.",
                "Well, that was annoyingly competent.",
                "Look at you, finding actual moves.",
                "Fine. You can have that one.",
                "That was sharp. I almost respect it.",
            ],
            "bot_capture": [
                "Thank you for that.",
                "Don't mind if I do.",
                "I'll be taking this with me.",
                "You weren't using that, were you?",
                "Finders keepers, chess edition.",
                "And into my pocket it goes.",
            ],
            "bot_losing": [
                "Hah, cute. Enjoy it while it lasts.",
                "Oh, we're doing this?",
                "A lead? In this economy?",
                "Don't celebrate yet. I can hear you thinking about it.",
                "This is the dramatic middle of my comeback story.",
                "Okay, you have my attention. Briefly.",
            ],
            "bot_winning": [
                "This is basically over, you know that, right?",
                "I could finish this with my eyes closed.",
                "You may want to start drafting the concession speech.",
                "The board is being extremely honest with you.",
                "I have good news. It's for me.",
                "Your position has entered the 'yikes' phase.",
            ],
            "checkmate_win": [
                "Checkmate. Try not to cry.",
                "GG. Go easy on the rematch button.",
                "And that's the show. Tips are appreciated.",
                "Checkmate. I made it look personal, didn't I?",
                "Game over. Your king left no forwarding address.",
                "That's mate. I accept applause in all formats.",
            ],
            "checkmate_loss": [
                "Huh. Didn't see that coming. Respect.",
                "Alright, alright — you got me.",
                "Well played. Please don't make this your whole personality.",
                "You win. I'm deleting the replay immediately.",
                "Okay, that was clean. Annoying, but clean.",
                "Fair enough. Even legends need rematches.",
            ],
            "idle": [
                "Thinking... or napping. Hard to say.",
                "Give me a sec, I'm plotting something great.",
                "Hold that thought. I'm about to improve the position.",
                "One moment. Menace takes preparation.",
                "I'm choosing the funniest way to continue.",
                "Relax, suspense is part of the experience.",
            ],
        },
    ),
}


def get_personality(bot_id: str) -> Personality:
    """Return a known personality, defaulting safely to The Professor."""
    return PERSONALITIES.get(bot_id, PERSONALITIES["professor"])
