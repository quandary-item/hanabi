from collections import Counter, defaultdict
from dataclasses import dataclass
import itertools
from typing import Any, DefaultDict, Dict, List, Literal


Colour = Literal['red', 'yellow', 'green', 'blue', 'white']
colour_values: List[Colour] = ['red', 'yellow', 'green', 'blue', 'white']
NumValue = Literal[1, 2, 3, 4, 5]
card_values: List[NumValue] = [1, 2, 3, 4, 5]
HintType = Literal['colour', 'value']

CARD_COUNTS = {
  colour: {1: 3, 2: 2, 3: 2, 4: 2, 5: 1}
  for colour in colour_values
}

ALL_CARD_IDS = range(5)


class GameOver(Exception):
  pass


@dataclass
class Card:
  colour: Colour
  value: NumValue

@dataclass
class Action:
  name: str
  args: Any


def possible_cards_from_hints(hints, card_counts):
  for colour, value in hints.keys():
    if hints[(colour, value)] and CARD_COUNTS[colour][value] - card_counts[colour][value] > 0:
      yield (colour, value)

def initial_hints():
  return {
    (colour, value): True
    for colour in colour_values
    for value in card_values
  }

class DiscardPile:
  def __init__(self) -> None:
    self.cards: List[Card] = []
    self.counts = Counter()

  def add_card(self, card):
    self.cards.append(card)
    self.counts[(card.colour, card.value)] += 1

  def get_count(self, colour, value):
    return self.counts[(colour, value)]

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
  def __init__(self, num_players: int, deck: List[Card]) -> None:
    self.num_players = num_players

    self.deck = deck
    self.discard_pile = DiscardPile()
    self.table: Dict[str, int] = {c: 0 for c in colour_values}

    self.hints_remaining = 8
    self.mistakes_remaining = 3

    self.hints = [[initial_hints() for card_id in ALL_CARD_IDS]
                   for player in range(self.num_players)]
    self.init_hands()

  def init_hands(self):
    self.hands = []
    for player_id in range(self.num_players):
      hand = []
      for i in ALL_CARD_IDS:
        card = self.deck.pop()
        hand.append(card)
      self.hands.append(hand)

  def get_score(self):
    return sum(self.table.values())

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
    for card_id in usable_cards:
      possible_cards = possible_cards_from_hints(player_hints[card_id], player_card_counts)

      can_discard = True
      for card_colour, card_value in possible_cards:
        num_cards_not_discarded = (CARD_COUNTS[card_colour][card_value] -
          self.discard_pile.get_count(card_colour, card_value))
        # if the card has already been played, then it can also be discarded
        already_played = card_value <= self.table[card_colour]
        if not already_played and num_cards_not_discarded == 1:
          can_discard = False
      if can_discard:
        yield card_id

  def get_card_ids_player_can_play_from_hints(self, usable_cards, player_hints, player_card_counts):
    required_cards = self.get_required_cards()

    for card_id in usable_cards:
      possible_cards = possible_cards_from_hints(player_hints[card_id], player_card_counts)
      if all([card in required_cards for card in possible_cards]):
        yield card_id

  def get_card_ids_player_can_discard(self, player_id):
    for card_id in self.get_usable_cards(player_id):
      card = self.hands[player_id][card_id]
      num_cards_not_discarded = (CARD_COUNTS[card.colour][card.value] -
        self.discard_pile.get_count(card.colour, card.value))
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

    card_counts = {colour: {v: 0 for v in card_values} for colour in colour_values}

    # add up counts in the discard pile
    for card in self.discard_pile.cards:
      card_counts[card.colour][card.value] += 1

    # add up counts on the table
    for colour, value in self.table.items():
      for v in range(1, value + 1):
        card_counts[colour][v] += 1

    # add up counts in the (not excluded) hands
    for player_id in range(self.num_players):
      if player_id not in exclude_hands:
        for card in self.hands[player_id]:
          if card:
            card_counts[card.colour][card.value] += 1

    return card_counts

  def is_card_on_table(self, card: Card):
    # returns True if a card with this colour and value is on the table
    table_value = self.table[card.colour]
    return card.value <= table_value

  def are_there_cards_remaining_of_this_type(self, card: Card):
    total_card_count = CARD_COUNTS[card.colour][card.value]
    return self.discard_pile.get_count(card.colour, card.value) < total_card_count

  def put_card_on_discard_pile(self, card: Card):
    # put it in the discard pile
    self.discard_pile.add_card(card)

    if not self.is_card_on_table(card):
      # print(f'discarded a card that has not been played yet {card}')
      if not self.are_there_cards_remaining_of_this_type(card):
        raise GameOver(f'the last copy of this card {card} has been discarded')

  def apply_action(self, player_id: int, action: Action):
    if not action:
      raise GameOver('no more actions')
    if action.name == 'discard':
      (card_id,) = action.args

      # take the card out of the hand
      card = self.hands[player_id][card_id]
      self.hands[player_id][card_id] = None

      # invalidate hint
      self.hints[player_id][card_id] = initial_hints()

      self.put_card_on_discard_pile(card)

      # increment number of remaining hints
      self.hints_remaining += 1

      # draw a new card
      if len(self.deck) > 0:
        new_card = self.deck.pop()
        self.hands[player_id][card_id] = new_card

    elif action.name == 'play':
      (card_id,) = action.args

      # take the card out of the hand
      card = self.hands[player_id][card_id]
      self.hands[player_id][card_id] = None

      # invalidate hint
      self.hints[player_id][card_id] = initial_hints()

      # can we play this card?
      # get the part of the table with the right colour
      if self.table[card.colour] + 1 == card.value:
        self.table[card.colour] += 1
      else:
        self.mistakes_remaining -= 1

        # put it in the discard pile
        self.put_card_on_discard_pile(card)

        if self.mistakes_remaining == 0:
          # lose
          raise GameOver('ran out of mistakes')
        # if we cannot win, abort
        pass
      # draw a new card
      if len(self.deck) > 0:
        new_card = self.deck.pop()
        self.hands[player_id][card_id] = new_card

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
