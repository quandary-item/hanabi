from collections import Counter, defaultdict
from dataclasses import dataclass
import itertools
import random
from colorama import Fore, init  # type: ignore
from typing import Any, DefaultDict, Dict, List, Literal, Optional, Set, Tuple


Colour = Literal['red', 'yellow', 'green', 'blue', 'white']
colour_values: List[Colour] = ['red', 'yellow', 'green', 'blue', 'white']
NumValue = Literal[1, 2, 3, 4, 5]
card_values: List[NumValue] = [1, 2, 3, 4, 5]
HintType = Literal['colour', 'value']

@dataclass
class Card:
  colour: Colour
  value: NumValue

@dataclass
class Action:
  name: str
  args: Any

# actions:
# play card
# give hint
# discard card
# action does not have the id of the player, that is implicit?


# Facts:
# card is [colour]
# card is not [colour]
# card is [value]
# card is not [value]


# Strategies
# if i know [facts], then do [action]
# if i know other person knows [facts], then do [action]

# Alternative approach:
# Tree search?

# 'knowledge base' approach
# there are facts that everyone knows (all of the hints, X card has been played/discarded)
# and facts that only a subset of players knows (X has a card in their hand)
# in order for a player to decide what to do, they need to deduce from the above facts
# so this is like a logic programming exercise


# TODO: if hints have been given for all of the cards in the other players hands, and you have no other
# actions you can take, then you can give a redundant hint

# TODO: if it is no longer possible to win (if a card that is needed on the table is discarded/played at
# the wrong time), then game over
# TODO: it looks like some hints are just plain wrong still? wtf?
# TODO: it looks like some cards are vanishing into the void?

# How do you describe what you know about the things that other people know?

CARD_COUNTS = {
  colour: {1: 3, 2: 2, 3: 2, 4: 2, 5: 1}
  for colour in colour_values
}

ALL_CARD_IDS = range(5)


class GameOver(Exception):
  pass


def create_deck() -> List[Card]:
  deck = []
  # three ones
  for c in colour_values:
    deck.append(Card(c, 1))
    deck.append(Card(c, 1))
    deck.append(Card(c, 1))

  # two twos, threes, fours
  middle_values: List[NumValue] = [2, 3, 4]
  for i in middle_values:
    for c in colour_values:
      deck.append(Card(c, i))
      deck.append(Card(c, i))

  # one five
  for c in colour_values:
    deck.append(Card(c, 5))

  random.shuffle(deck)
  return deck


class PlayerKnowledge:
  def __init__(self, index):
    self.index = index
    self.card_counts = {colour: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0} for colour in colour_values}

  def see_card(self, card):
    # Call this when somebody drew a card
    self.card_counts[card.colour][card.value] += 1

def initial_hints():
  return {
    (colour, value): True
    for colour in colour_values
    for value in card_values
  }

def apply_hint(do_hint: bool, card_hints, hint_type, hint_value):
  if hint_type == 'colour':
    extract = lambda card: card[0]
  else:
    extract = lambda card: card[1]

  # Send the hint to the other players
  return {
    card: False if (
      (extract(card) != hint_value and do_hint) or
      (extract(card) == hint_value and not do_hint)
    ) else card_hints[card]

    for card in itertools.product(colour_values, card_values)
  }

class GameState:
  def __init__(self, players: List[PlayerKnowledge]) -> None:
    self.players = players

    self.deck = create_deck()
    self.discard_pile: List[Card] = []
    self.table: Dict[str, int] = {c: 0 for c in colour_values}

    self.hints_remaining = 8
    self.mistakes_remaining = 3

    self.init_hands()
    self.init_hints()

  def init_hints(self):
    self.hints = []
    for player in self.players:
      player_hints = []
      for card_id in ALL_CARD_IDS:
        player_hints.append(initial_hints())

      self.hints.append(player_hints)

  def init_hands(self):
    self.hands = []
    for player_id, player in enumerate(self.players):
      hand = []
      for i in ALL_CARD_IDS:
        card = self.deck.pop()
        hand.append(card)
        for other_player_id, other_player in enumerate(self.players):
          if player_id != other_player_id:
            other_player.see_card(card)
      self.hands.append(hand)

  def get_usable_cards(self, player_id: int):
    result = []
    for i, card in enumerate(self.hands[player_id]):
      if card:
        result.append(i)
    return result

  def get_available_actions(self, player_id: int) -> List[Action]:
    actions = []

    # discard any of the cards in their hand
    hand = self.hands[player_id]
    for i, card in enumerate(hand):
      if card:
        actions.append(Action('discard', [i]))

    # play any of the cards
    for i, card in enumerate(hand):
      if card:
        actions.append(Action('play', [i]))

    if self.hints_remaining > 0:
      # give a hint to any other player (if there are enough hint tokens left)
      for other_player_id, other_hand in enumerate(self.hands):
        card_ids_by_colour: DefaultDict[str, List[int]] = defaultdict(list)
        card_ids_by_value: DefaultDict[int, List[int]] = defaultdict(list)

        for card_id, card in enumerate(other_hand):
          if card:
            card_ids_by_colour[card.colour].append(card_id)
            card_ids_by_value[card.value].append(card_id)

        for colour, card_ids in card_ids_by_colour.items():
          actions.append(Action('hint', [other_player_id, card_ids, 'colour', colour]))

        for value, card_ids in card_ids_by_value.items():
          actions.append(Action('hint', [other_player_id, card_ids, 'value', value]))

    return actions

  def get_required_cards(self):
    required_cards = set()
    for k, v in self.table.items():
      if v < 5:
        required_cards.add((k, v + 1))
    return required_cards

  def get_card_ids_player_can_discard_from_hints(self, usable_cards, player_hints, player_card_counts):
    discard_pile_counts = Counter([(card.colour, card.value) for card in self.discard_pile])

    for card_id in usable_cards:
      possible_cards = set(
        possible_cards_from_hints(player_hints[card_id], player_card_counts)
      )

      can_discard = True
      for card_colour, card_value in possible_cards:
        num_cards_not_discarded = CARD_COUNTS[card_colour][card_value] - discard_pile_counts[(card_colour, card_value)]
        # if the card has already been played, then it can also be discarded
        already_played = card_value <= self.table[card_colour]
        if not already_played and num_cards_not_discarded == 1:
          can_discard = False
      if can_discard:
        yield card_id

  def get_card_ids_player_can_play_from_hints(self, usable_cards, player_hints, player_card_counts):
    required_cards = self.get_required_cards()

    for card_id in usable_cards:
      possible_cards = set(
        possible_cards_from_hints(player_hints[card_id], player_card_counts)
      )
      if all([card in required_cards for card in possible_cards]):
        yield card_id

  def get_card_ids_player_can_discard(self, player_id):
    discard_pile_counts = Counter([(card.colour, card.value) for card in self.discard_pile])

    for card_id in self.get_usable_cards(player_id):
      card = self.hands[player_id][card_id]
      num_cards_not_discarded = CARD_COUNTS[card.colour][card.value] - discard_pile_counts[(card.colour, card.value)]
      already_played = card.value <= self.table[card.colour]
      if not already_played and num_cards_not_discarded > 1:
        yield card_id

  def get_card_ids_player_can_play(self, player_id):
    required_cards = self.get_required_cards()
    for card_id in self.get_usable_cards(player_id):
      card = self.hands[player_id][card_id]
      if (card.colour, card.value) in required_cards:
        yield card_id

  def get_card_counts(self, exclude_hands=None):
    exclude_hands = exclude_hands or []

    card_counts = {colour: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0} for colour in colour_values}

    # add up counts in the discard pile
    for card in self.discard_pile:
      card_counts[card.colour][card.value] += 1

    # add up counts on the table
    for colour, value in self.table.items():
      for v in range(1, value + 1):
        card_counts[colour][v] += 1

    # add up counts in the (not excluded) hands
    for player_id, player in enumerate(self.players):
      if player_id not in exclude_hands:
        for card in self.hands[player_id]:
          if card:
            card_counts[card.colour][card.value] += 1

    return card_counts


  def select_action_ai(self, last_move: Action, player_id: int, actions: List[Action]):

    # some strategies
    # - "avoid failure": with the information that the current player has, guess what the next player would do
    #   if the next player would do something that 1. causes them to lose the game 2. causes a mistake to happen
    #   then give them a hint so that that doesn't happen. this could allow us to be a little bit more loose with
    #   the play/discard logic. also this would be useful if the number of available hints is a low number
    # - "play for success": look at the required cards, if the next player could play any of them, then give them
    #   a hint
    # - "allow discards": if the other players are able to discard any cards, then give them a hint (useful for
    #   replenishing hints?)

    # - "remember hints": e.g if a player gave you a hint that you have a "one" and since then nobody has played
    #   a one, then assume you can play that card. same goes for other colours etc. also need to change logic so
    #   that players aren't given redundant hints?

    # if you have a card you know can be played (using hints + card counting), then play it
    # print(f'required cards: {required_cards}')

    if last_move:

      pass


    usable_cards = self.get_usable_cards(player_id)
    player_hints = self.hints[player_id]
    player_card_counts = self.get_card_counts(exclude_hands=[player_id])

    cards_to_play = list(self.get_card_ids_player_can_play_from_hints(usable_cards, player_hints, player_card_counts))
    if cards_to_play:
      action = [a for a in actions if a.name == 'play' and a.args[0] in cards_to_play][0]
      return action

    cards_to_discard = list(self.get_card_ids_player_can_discard_from_hints(usable_cards, player_hints, player_card_counts))
    if cards_to_discard:
      action = [a for a in actions if a.name == 'discard' and a.args[0] in cards_to_discard][0]
      return action

    # print(f'can discard: {cards_to_discard}')
    # print(f'can play: {cards_to_play}')

    if self.hints_remaining == 0:
      return random.choice(actions)

    # give a hint
    # iterate over the other players, starting with the next player
    num_players = len(self.players)
    for i in range(1, num_players):
      other_player_id = (i + player_id) % num_players

      print(f'thinking of hints for {other_player_id}')

      # does the other player have any cards that can be played now?
      can_play_ids = set(self.get_card_ids_player_can_play(other_player_id))
      can_discard_ids = set(self.get_card_ids_player_can_discard(other_player_id))

      # check if this card is 'covered' by the hints
      cards_that_need_hints = set()

      play_hints_needed = defaultdict(set)
      # print(f'can play ids: {can_play_ids}')
      # print(f'can discard ids: {can_discard_ids}')
      for card_id in can_play_ids:
        card = self.hands[other_player_id][card_id]

        for colour in colour_values:
          for value in card_values:
            if colour != card.colour:
              if self.hints[other_player_id][card_id][(colour, value)]:
                play_hints_needed[card.colour].add(card_id)
                cards_that_need_hints.add(card_id)

            if value != card.value:
              if self.hints[other_player_id][card_id][(colour, value)]:
                play_hints_needed[card.value].add(card_id)
                cards_that_need_hints.add(card_id)

      discard_hints_needed = defaultdict(set)
      # print(f'can play ids: {can_play_ids}')
      # print(f'can discard ids: {can_discard_ids}')
      for card_id in can_discard_ids:
        card = self.hands[other_player_id][card_id]

        for colour in colour_values:
          for value in card_values:
            if colour != card.colour:
              if self.hints[other_player_id][card_id][(colour, value)]:
                discard_hints_needed[card.colour].add(card_id)
                cards_that_need_hints.add(card_id)

            if value != card.value:
              if self.hints[other_player_id][card_id][(colour, value)]:
                discard_hints_needed[card.value].add(card_id)
                cards_that_need_hints.add(card_id)

      self.players[player_id].card_counts

      other_player_usable_cards = self.get_usable_cards(other_player_id)
      other_player_card_counts = self.get_card_counts(exclude_hands=[player_id, other_player_id])

      good_discard_hints = {}
      for hint_value, card_ids_to_hint in (discard_hints_needed).items():
        hint_type = 'colour' if hint_value in colour_values else 'value'
        updated_hints = [
          apply_hint(
            card_id in card_ids_to_hint,
            self.hints[other_player_id][card_id],
            hint_type,
            hint_value
          )
          for card_id in range(5)
        ]
        # if the hint is applied, would the new cards be in
        # but use the current player's card counts, because the current playet doesn't know how many cards the other player has seen
        cards_that_can_be_discarded = list(self.get_card_ids_player_can_discard_from_hints(
          other_player_usable_cards, updated_hints, other_player_card_counts))
        if cards_that_can_be_discarded:
          good_discard_hints[hint_value] = cards_that_can_be_discarded

      good_play_hints = {}
      for hint_value, card_ids_to_hint in (play_hints_needed).items():
        hint_type = 'colour' if hint_value in colour_values else 'value'
        updated_hints = [
          apply_hint(
            card_id in card_ids_to_hint,
            self.hints[other_player_id][card_id],
            hint_type,
            hint_value
          )
          for card_id in range(5)
        ]

        # if the hint is applied, would the new cards be in
        # but use the current player's card counts, because the current playet doesn't know how many cards the other player has seen
        cards_that_can_be_played = list(self.get_card_ids_player_can_play_from_hints(
          other_player_usable_cards, updated_hints, other_player_card_counts))
        if cards_that_can_be_played:
          good_play_hints[hint_value] = cards_that_can_be_played

      print(f'discard hints: {discard_hints_needed}')
      print(f'play hints: {play_hints_needed}')
      print(f'good discard hints: {good_discard_hints}')
      print(f'good play hints: {good_play_hints}')

      # choose the hint that is needed by the most cards
      cards_that_dont_need_hints = (can_play_ids | can_discard_ids) - cards_that_need_hints
      if len(cards_that_dont_need_hints) == 0:
        if discard_hints_needed:
          if good_discard_hints:
            best_hint = list(good_discard_hints.keys())[0]
          else:
            best_hint = max(discard_hints_needed.keys(), key=lambda k: len(discard_hints_needed[k]))
          hint_action = [a for a in actions if a.name == 'hint' and a.args[0] == other_player_id and a.args[3] == best_hint][0]
          return hint_action
        elif play_hints_needed:
          if good_play_hints:
            best_hint = list(good_play_hints.keys())[0]
          else:
            best_hint = max(play_hints_needed.keys(), key=lambda k: len(play_hints_needed[k]))
          hint_action = [a for a in actions if a.name == 'hint' and a.args[0] == other_player_id and a.args[3] == best_hint][0]
          return hint_action

        # pick a hint if there aren't any cards that can be played next


  def apply_action(self, player_id: int, action: Action):
    if action.name == 'discard':
      (card_id,) = action.args

      # take the card out of the hand
      card = self.hands[player_id][card_id]
      self.hands[player_id][card_id] = None

      # invalidate hint
      self.hints[player_id][card_id] = initial_hints()

      # other players see card
      for player in self.players:
        if player.index != player_id:
          player.see_card(card)

      # put it in the discard pile
      self.discard_pile.append(card)

      # increment number of remaining hints
      self.hints_remaining += 1

      # draw a new card
      if len(self.deck) > 0:
        self.hands[player_id][card_id] = self.deck.pop()

    elif action.name == 'play':
      (card_id,) = action.args

      # take the card out of the hand
      card = self.hands[player_id][card_id]
      self.hands[player_id][card_id] = None

      # invalidate hint
      self.hints[player_id][card_id] = initial_hints()

      # other players see card
      for player in self.players:
        if player.index != player_id:
          player.see_card(card)

      # can we play this card?
      # get the part of the table with the right colour
      if self.table[card.colour] + 1 == card.value:
        self.table[card.colour] += 1
      else:
        self.mistakes_remaining -= 1

        if self.mistakes_remaining == 0:
          # lose
          raise GameOver('ran out of mistakes')
        # if we cannot win, abort
        pass
      # draw a new card
      if len(self.deck) > 0:
        self.hands[player_id][card_id] = self.deck.pop()

    elif action.name == 'hint':
      self.hints_remaining -= 1
      (other_player_id, card_ids_to_hint, hint_type, hint_value) = action.args

      self.hints[other_player_id] = [
        apply_hint(
          card_id in card_ids_to_hint,
          self.hints[other_player_id][card_id],
          hint_type,
          hint_value
        )
        for card_id in range(5)
      ]


colour_code = {'red': Fore.RED, 'yellow': Fore.YELLOW, 'green': Fore.GREEN, 'blue': Fore.BLUE, 'white': Fore.BLACK}

def format_deck(deck: List[Card]):
  parts = []
  for c in deck:
    parts.append(colour_code[c.colour])
    parts.append(str(c.value))
    parts.append(' ')

  return ''.join(parts)

def format_table(table):
  parts = []
  for value in colour_values:
    parts.append(colour_code[value])
    parts.append(str(table[value]) or '-')
    parts.append(' ')
  return ''.join(parts)

def format_hand(hand):
  parts = []
  for card in hand:
    if card:
      parts.append(colour_code[card.colour])
      parts.append(str(card.value))
    else:
      parts.append(' ')
  return ''.join(parts)

def format_hints(player_hints, card_counts):
  for colour in colour_values:
    for card_id in ALL_CARD_IDS:
      yield Fore.BLACK
      yield '|'
      for value in card_values:
        if player_hints[card_id][(colour, value)]:
          yield colour_code[colour]

          # num cards that have not been seen or played/discarded
          num_cards_remaining = CARD_COUNTS[colour][value] - card_counts[colour][value]
          if num_cards_remaining == 3:
            yield str(value) * 3
          elif num_cards_remaining == 2:
            yield str(value) * 2 + ' '
          elif num_cards_remaining == 1:
            yield str(value) + '  '
          else:
            yield '   '
        else:
          yield '   '
    yield Fore.BLACK
    yield '|'
    yield '\n'

def get_int():
  done = False
  while not done:
    try:
      result = int(input().strip())
      done = True
    except Exception as e:
      print(e)
      print('Invalid value, please retry: ')

  return result

def select_action(hands, actions: List[Action]):
  print('Which type of action do you want to perform?')
  print('1. discard')
  print('2. play')
  print('3. hint')
  selected_action_type = get_int()
  if selected_action_type == 1:
    available_cards_to_discard = [action.args[0] for action in actions if action.name == 'discard']
    print(f'Which card would you like to discard? {available_cards_to_discard}')
    card_id = get_int()
    action = Action('discard', [card_id])
  elif selected_action_type == 2:
    available_cards_to_play = [action.args[0] for action in actions if action.name == 'play']
    print(f'Which card would you like to play? {available_cards_to_play}')
    card_id = get_int()
    action = Action('play', [card_id])

  else:
    available_players_to_hint = sorted(set([action.args[0] for action in actions if action.name == 'hint']))
    print(f'Which player would you like to hint? {available_players_to_hint}')
    other_player_id = get_int()

    print(f'Player {other_player_id}\'s cards: ' + format_hand(hands[other_player_id]) + Fore.BLACK)

    available_hints = [action for action in actions if action.name == 'hint' and action.args[0] == other_player_id]

    for hint_action_id, hint_action in enumerate(available_hints):
      print(f'{hint_action_id}: Cards {hint_action.args[1]} are {hint_action.args[3]}')

    print('Which hint would you like to choose?')

    hint_id = get_int()
    action = available_hints[hint_id]

  return action


def possible_cards_from_hints(hints, card_counts):
  for colour, value in hints.keys():
    if hints[(colour, value)] and CARD_COUNTS[colour][value] - card_counts[colour][value] > 0:
      yield (colour, value)


def run():
  num_players = 5
  current_player = 0

  game = GameState([PlayerKnowledge(i) for i in range(num_players)])
  print(format_deck(game.deck))

  while True:
    actions = game.get_available_actions(current_player)

    if not actions:
      # no more actions
      print('no more available actions')
      break

    print(Fore.BLACK + 'Current player', str(current_player))
    print('hints:')
    for player_id in range(num_players):
      print(player_id, 'hints')
      print(''.join(format_hints(game.hints[player_id], game.players[current_player].card_counts)))
    # print('deck:', format_deck(game.deck))
    print('discard pile:', format_deck(game.discard_pile))
    print(Fore.BLACK + 'table:', format_table(game.table))
    print('hints remaining:', game.hints_remaining)
    print('mistakes remaining:', game.mistakes_remaining)

    # for each card in the player's hand
    # figure out what values the card could have
    # figure out if the game would end if the card was played / discarded
    # and turned out to be the wrong card
    # compared probabilities
    for i, hand in enumerate(game.hands):
      if i == current_player:
        print('*', format_hand(hand), Fore.BLACK)
      else:
        print(' ', format_hand(hand), Fore.BLACK)

    # selected_action_i = get_int()
    action = game.select_action_ai(None, current_player, actions)

    if not action:
      print('game over: there are no more available actions')
      return
    print(f'ai recommended action:{action}')

    # action = actions[selected_action_i]
    # action = select_action(game.hands, actions)
    print(Fore.BLACK + str(action), len(game.deck))

    try:
      game.apply_action(current_player, action)
    except GameOver as e:
      print('game over:', e)
      return
    current_player = (current_player + 1) % num_players


if __name__ == '__main__':
  init()
  run()