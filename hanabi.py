from collections import defaultdict
import random
from colorama import Fore, init  # type: ignore
from typing import List

from gamestate import Action, Card, GameOver, GameState, NumValue, colour_values, card_values, apply_hint, CARD_COUNTS

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
# TODO: it looks like some hints are just plain wrong still? wtf?
# TODO: consider opening/middlegame/endgame strategy - should different things be prioritised?
# TODO: consider tree search of some kind
# TODO: make this faster, it's so slow

# How do you describe what you know about the things that other people know?

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

class AI():
  def select_action_ai(self, game: GameState, last_move: Action, player_id: int, actions: List[Action]):

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

    usable_cards = game.get_usable_cards(player_id)
    player_hints = game.hints[player_id]
    player_card_counts = game.get_card_counts(exclude_hands=[player_id])

    for card_id in game.get_card_ids_player_can_play_from_hints(usable_cards, player_hints, player_card_counts):
      action = [a for a in actions if a.name == 'play' and a.args[0] == card_id][0]
      return action

    for card_id in game.get_card_ids_player_can_discard_from_hints(usable_cards, player_hints, player_card_counts):
      action = [a for a in actions if a.name == 'discard' and a.args[0] == card_id][0]
      return action

    # print(f'can discard: {cards_to_discard}')
    # print(f'can play: {cards_to_play}')

    if game.hints_remaining == 0:
      return random.choice(actions) if actions else None

    # give a hint
    # iterate over the other players, starting with the next player
    for i in range(1, game.num_players):
      other_player_id = (i + player_id) % game.num_players

      # print(f'thinking of hints for {other_player_id}')

      # does the other player have any cards that can be played now?
      can_play_ids = set(game.get_card_ids_player_can_play(other_player_id))
      can_discard_ids = set(game.get_card_ids_player_can_discard(other_player_id))

      # check if this card is 'covered' by the hints
      cards_that_need_hints = set()

      play_hints_needed = defaultdict(set)
      # print(f'can play ids: {can_play_ids}')
      # print(f'can discard ids: {can_discard_ids}')
      for card_id in can_play_ids:
        card = game.hands[other_player_id][card_id]

        for colour in colour_values:
          for value in card_values:
            if colour != card.colour:
              if game.hints[other_player_id][card_id][(colour, value)]:
                play_hints_needed[card.colour].add(card_id)
                cards_that_need_hints.add(card_id)

            if value != card.value:
              if game.hints[other_player_id][card_id][(colour, value)]:
                play_hints_needed[card.value].add(card_id)
                cards_that_need_hints.add(card_id)

      discard_hints_needed = defaultdict(set)
      # print(f'can play ids: {can_play_ids}')
      # print(f'can discard ids: {can_discard_ids}')
      for card_id in can_discard_ids:
        card = game.hands[other_player_id][card_id]

        for colour in colour_values:
          for value in card_values:
            if colour != card.colour:
              if game.hints[other_player_id][card_id][(colour, value)]:
                discard_hints_needed[card.colour].add(card_id)
                cards_that_need_hints.add(card_id)

            if value != card.value:
              if game.hints[other_player_id][card_id][(colour, value)]:
                discard_hints_needed[card.value].add(card_id)
                cards_that_need_hints.add(card_id)

      other_player_usable_cards = game.get_usable_cards(other_player_id)
      other_player_card_counts = game.get_card_counts(exclude_hands=[player_id, other_player_id])

      good_discard_hints = {}
      for hint_value, card_ids_to_hint in (discard_hints_needed).items():
        hint_type = 'colour' if hint_value in colour_values else 'value'
        updated_hints = [
          apply_hint(
            card_id in card_ids_to_hint,
            game.hints[other_player_id][card_id],
            hint_type,
            hint_value
          )
          for card_id in range(5)
        ]
        # if the hint is applied, would the new cards be in
        # but use the current player's card counts, because the current playet doesn't know how many cards the other player has seen
        cards_that_can_be_discarded = list(game.get_card_ids_player_can_discard_from_hints(
          other_player_usable_cards, updated_hints, other_player_card_counts))
        if cards_that_can_be_discarded:
          good_discard_hints[hint_value] = cards_that_can_be_discarded

      good_play_hints = {}
      for hint_value, card_ids_to_hint in (play_hints_needed).items():
        hint_type = 'colour' if hint_value in colour_values else 'value'
        updated_hints = [
          apply_hint(
            card_id in card_ids_to_hint,
            game.hints[other_player_id][card_id],
            hint_type,
            hint_value
          )
          for card_id in range(5)
        ]

        # if the hint is applied, would the new cards be in
        # but use the current player's card counts, because the current playet doesn't know how many cards the other player has seen
        cards_that_can_be_played = list(game.get_card_ids_player_can_play_from_hints(
          other_player_usable_cards, updated_hints, other_player_card_counts))
        if cards_that_can_be_played:
          good_play_hints[hint_value] = cards_that_can_be_played

      # print(f'discard hints: {discard_hints_needed}')
      # print(f'play hints: {play_hints_needed}')
      # print(f'good discard hints: {good_discard_hints}')
      # print(f'good play hints: {good_play_hints}')

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

def format_hints(hand, player_hints, card_counts):
  for colour in colour_values:
    for card_id in range(5):
      yield Fore.BLACK
      yield '|'

      if hand[card_id]:
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
      else:
        for value in card_values:
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


def run():
  num_players = 5
  current_player = 0

  game = GameState(num_players, create_deck())
  ai = AI()

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
      print(''.join(format_hints(game.hands[player_id], game.hints[player_id], game.get_card_counts(exclude_hands=[player_id]))))
    # print('deck:', format_deck(game.deck))
    print('discard pile:', format_deck(game.discard_pile.cards))
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


    # # hint sanity check
    # for card_id in game.get_usable_cards(current_player):
    #   card = game.hands[current_player][card_id]
    #   if not game.hints[current_player][card_id][(card.colour, card.value)]:
    #     print(f'the hint for card {card_id} in {current_player}\'s hand is wrong')
    #     import ipdb;ipdb.set_trace()
    #   count_seen = game.players[current_player].card_counts[card.colour][card.value]
    #   total_count = CARD_COUNTS[card.colour][card.value]
    #   if total_count - count_seen == 0:
    #     print(f'the count for {card_id} in {current_player}\'s hand is wrong')
    #     print(card_id, total_count - count_seen, card)
    #     import ipdb;ipdb.set_trace()

    # selected_action_i = get_int()
    action = ai.select_action_ai(game, None, current_player, actions)

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


def bulk_run():
  num_players = 5
  current_player = 0

  game = GameState(num_players, create_deck())
  ai = AI()
  # print(format_deck(game.deck))

  while True:
    actions = game.get_available_actions(current_player)
    action = ai.select_action_ai(game, None, current_player, actions)

    try:
      game.apply_action(current_player, action)
    except GameOver as e:
      print(Fore.BLACK + 'table:', format_table(game.table))
      print('game over:', e)
      break
    current_player = (current_player + 1) % num_players
  score = game.get_score()
  print(f'score: {score}')
  return score


if __name__ == '__main__':
  init()
  num_games = 100
  scores = []
  for i in range(num_games):
    score = bulk_run()
    scores.append(score)
  print(scores)
  print(f'highest score: {max(scores)}')
  print(f'lowest score: {min(scores)}')
  print(f'mean score: {sum(scores) / num_games}')