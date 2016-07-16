from itertools import cycle
import random
import sys

import gs
import gs.plus.render as render
import gs.plus.clock as clock

SCREENWIDTH = 288
SCREENHEIGHT = 512
# amount by which base can maximum shift to left
PIPEGAPSIZE = 150 # gap between upper and lower part of pipe
BASEY = SCREENHEIGHT * 0.79
# image, sound and hitmask  dicts
IMAGES, SOUNDS, HITMASKS = {}, {}, {}

# list of all possible players (tuple of 3 positions of flap)
PLAYERS_LIST = []
for bird_col in ['red', 'blue', 'yellow']:
	PLAYERS_LIST.append([
		'@assets/sprites/{0}bird-upflap.png'.format(bird_col),
		'@assets/sprites/{0}bird-midflap.png'.format(bird_col),
		'@assets/sprites/{0}bird-downflap.png'.format(bird_col)])

# list of backgrounds
BACKGROUNDS_LIST = (
	'@assets/sprites/background-day.png',
	'@assets/sprites/background-night.png',
)

# list of pipes
PIPES_LIST = (
	'@assets/sprites/pipe-green.png',
	'@assets/sprites/pipe-red.png',
	'@assets/sprites/pipe-green-yflip.png',
	'@assets/sprites/pipe-red-yflip.png',	
)


# ------------------------------------------------------------------------------
def sprite2dtex(tex, x: float, y: float, size: float = 1.0, color=gs.Color.White, pivot_x: float = 0.5,
			 pivot_y: float = 0.5, flip_h: bool = False, flip_v: bool = False):
	x -= size * pivot_x
	y -= size * pivot_y

	render.texture2d(x, y, size, tex, color, flip_h, not flip_v)


def main():
	global al, keyboard

	# load plugins
	gs.LoadPlugins(gs.get_default_plugins_path())
	# init the screen window
	render.init(SCREENWIDTH, SCREENHEIGHT, "pkg.core")
	render.set_2d_origin_is_top_left(True)
	# mount the system file driver
	gs.MountFileDriver(gs.StdFileDriver("assets/"), "@assets/")
	# open the audio mixer
	al = gs.ALMixer()
	al.Open()
	# open keyboard device
	keyboard = gs.GetInputSystem().GetDevice("keyboard")

	# numbers sprites for score display
	IMAGES['numbers'] = []
	for i in range(10):
		IMAGES['numbers'].append(render.get_renderer().LoadTexture('@assets/sprites/{0}.png'.format(i)))

	# game over, message and ground sprites
	for key in ['gameover', 'message', 'base']:
		IMAGES[key] = render.get_renderer().LoadTexture('@assets/sprites/{0}.png'.format(key))

	# sounds
	for key in ['die', 'hit', 'point', 'swoosh', 'wing']:
		SOUNDS[key] = al.LoadSound('@assets/audio/' + key + '.wav')

	while True:
		# select random background sprites
		rand_bg = random.randint(0, len(BACKGROUNDS_LIST) - 1)
		IMAGES['background'] = render.get_renderer().LoadTexture(BACKGROUNDS_LIST[rand_bg]) 

		# select random player sprites
		rand_player = random.randint(0, len(PLAYERS_LIST) - 1)
		IMAGES['player'] = (
			render.get_renderer().LoadTexture(PLAYERS_LIST[rand_player][0]),
			render.get_renderer().LoadTexture(PLAYERS_LIST[rand_player][1]),
			render.get_renderer().LoadTexture(PLAYERS_LIST[rand_player][2])
		)

		# select random pipe sprites
		pipe_index = random.randint(0, 1)
		IMAGES['pipe'] = (
			render.get_renderer().LoadTexture(PIPES_LIST[pipe_index + 2]),
			render.get_renderer().LoadTexture(PIPES_LIST[pipe_index])
		)

		# hismask for pipes
		HITMASKS['pipe'] = (
			get_bitmap_hitmask(IMAGES['pipe'][0]),
			get_bitmap_hitmask(IMAGES['pipe'][1])
		)

		# hitmask for player
		HITMASKS['player'] = (
			get_bitmap_hitmask(IMAGES['player'][0]),
			get_bitmap_hitmask(IMAGES['player'][1]),
			get_bitmap_hitmask(IMAGES['player'][2]),
		)

		movement_info = show_welcome_animation()
		crash_info = main_game_loop(movement_info)
		show_game_over_screen(crash_info)


def show_welcome_animation():
	"""Shows welcome screen animation of flappy bird"""
	# index of player to blit on screen
	player_index = 0
	player_index_gen = cycle([0, 1, 2, 1])
	# iterator used to change player_index after every 5th iteration
	loop_iter = 0

	playerx = int(SCREENWIDTH * 0.2)
	playery = int((SCREENHEIGHT - IMAGES['player'][0].GetHeight()) / 2)

	messagex = int((SCREENWIDTH - IMAGES['message'].GetWidth()) / 2)
	messagey = int(SCREENHEIGHT * 0.12)

	basex = 0
	# amount by which base can maximum shift to left
	base_shift = IMAGES['base'].GetWidth() - IMAGES['background'].GetWidth()

	# player shm for up-down motion on welcome screen
	player_frame = {'val': 0, 'dir': 1}

	while True:
		render.clear()

		render.set_blend_mode2d(render.BlendAlpha)

		# for event in pygame.event.get():
		if keyboard.WasPressed(gs.InputDevice.KeyEscape):
			# pygame.quit()
			sys.exit()
		if keyboard.WasPressed(gs.InputDevice.KeySpace):
			# make first flap sound and return values for main_game_loop
			al.Start(SOUNDS['wing'])
			return {
				'playery': playery + player_frame['val'],
				'basex': basex,
				'player_index_gen': player_index_gen,
			}

		# adjust playery, player_index, basex
		if (loop_iter + 1) % 5 == 0:
			player_index = next(player_index_gen)
		loop_iter = (loop_iter + 1) % 30
		basex = -((-basex + 4) % base_shift)
		player_oscillate(player_frame)

		# draw sprites
		sprite2dtex(IMAGES['background'], 0, 0)
		sprite2dtex(IMAGES['player'][player_index],
					playerx, playery + player_frame['val'])
		sprite2dtex(IMAGES['message'], messagex, messagey)
		sprite2dtex(IMAGES['base'], basex, BASEY)

		render.set_blend_mode2d(render.BlendOpaque)

		render.flip()
		clock.update()


def main_game_loop(movement_info):
	score = player_index = loop_iter = 0
	player_index_gen = movement_info['player_index_gen']
	playerx, playery = int(SCREENWIDTH * 0.2), movement_info['playery']

	basex = movement_info['basex']
	base_shift = IMAGES['base'].GetWidth() - IMAGES['background'].GetWidth()

	# get 2 new pipes to add to upper_pipes lower_pipes list
	new_pipe_1 = get_random_pipe()
	new_pipe_2 = get_random_pipe()

	# list of upper pipes
	upper_pipes = [
		{'x': SCREENWIDTH + 200, 'y': new_pipe_1[0]['y']},
		{'x': SCREENWIDTH + 200 + (SCREENWIDTH / 2), 'y': new_pipe_2[0]['y']},
	]

	# list of lowerpipe
	lower_pipes = [
		{'x': SCREENWIDTH + 200, 'y': new_pipe_1[1]['y']},
		{'x': SCREENWIDTH + 200 + (SCREENWIDTH / 2), 'y': new_pipe_2[1]['y']},
	]

	pipe_vel_x = -4

	# player velocity, max velocity, downward accleration, accleration on flap
	player_vel_y    =  -9   # player's velocity along Y, default same as player_flapped
	player_max_vel_y =  10   # max vel along Y, max descend speed
	# player_min_vel_y =  -8   # min vel along Y, max ascend speed
	player_acc_y    =   1   # players downward accleration
	player_flap_acc =  -9   # players speed on flapping
	player_flapped = False # True when player flaps


	while True:
		if gs.GetKeyboard().WasPressed(gs.InputDevice.KeyEscape):
			sys.exit()
		if gs.GetKeyboard().WasPressed(gs.InputDevice.KeySpace) or gs.GetKeyboard().WasPressed(gs.InputDevice.KeyUp):
			if playery > -2 * IMAGES['player'][0].GetHeight():
				player_vel_y = player_flap_acc
				player_flapped = True
				al.Start(SOUNDS['wing'])

		# check for crash here
		crash_test = check_collision({'x': playerx, 'y': playery, 'index': player_index},
							   upper_pipes, lower_pipes)
		if crash_test[0]:
			return {
				'y': playery,
				'groundCrash': crash_test[1],
				'basex': basex,
				'upper_pipes': upper_pipes,
				'lower_pipes': lower_pipes,
				'score': score,
				'player_vel_y': player_vel_y,
			}

		# check for score
		player_mid_pos = playerx + IMAGES['player'][0].GetWidth() / 2
		for pipe in upper_pipes:
			pipe_mid_pos = pipe['x'] + IMAGES['pipe'][0].GetWidth() / 2
			if pipe_mid_pos <= player_mid_pos < pipe_mid_pos + 4:
				score += 1
				al.Start(SOUNDS['point'])

		# player_index basex change
		if (loop_iter + 1) % 3 == 0:
			player_index = next(player_index_gen)
		loop_iter = (loop_iter + 1) % 30
		basex = -((-basex + 100) % base_shift)

		# player's movement
		if player_vel_y < player_max_vel_y and not player_flapped:
			player_vel_y += player_acc_y
		if player_flapped:
			player_flapped = False
		player_height = IMAGES['player'][player_index].GetHeight()
		playery += min(player_vel_y, BASEY - playery - player_height)

		# move pipes to left
		for u_pipe, l_pipe in zip(upper_pipes, lower_pipes):
			u_pipe['x'] += pipe_vel_x
			l_pipe['x'] += pipe_vel_x

		# add new pipe when first pipe is about to touch left of screen
		if 0 < upper_pipes[0]['x'] < 5:
			new_pipe = get_random_pipe()
			upper_pipes.append(new_pipe[0])
			lower_pipes.append(new_pipe[1])

		# remove first pipe if its out of the screen
		if upper_pipes[0]['x'] < -IMAGES['pipe'][0].GetWidth():
			upper_pipes.pop(0)
			lower_pipes.pop(0)

		# draw sprites
		sprite2dtex(IMAGES['background'], 0, 0)

		for u_pipe, l_pipe in zip(upper_pipes, lower_pipes):
			sprite2dtex(IMAGES['pipe'][0], u_pipe['x'], u_pipe['y'])
			sprite2dtex(IMAGES['pipe'][1], l_pipe['x'], l_pipe['y'])

		sprite2dtex(IMAGES['base'], basex, BASEY)
		# print score so player overlaps the score
		show_score(score)
		sprite2dtex(IMAGES['player'][player_index], playerx, playery)

		render.flip()
		clock.update()


def show_game_over_screen(crash_info):
	"""crashes the player down ans shows game over image"""
	score = crash_info['score']
	playerx = SCREENWIDTH * 0.2
	playery = crash_info['y']
	player_height = IMAGES['player'][0].GetHeight()
	player_vel_y = crash_info['player_vel_y']
	player_acc_y = 2

	basex = crash_info['basex']

	upper_pipes, lower_pipes = crash_info['upper_pipes'], crash_info['lower_pipes']

	# play hit and die sounds
	al.Start(SOUNDS['hit'])
	if not crash_info['groundCrash']:
		al.Start(SOUNDS['die'])

	while True:
		if gs.GetKeyboard().WasPressed(gs.InputDevice.KeyEscape):
			sys.exit()
		if gs.GetKeyboard().WasPressed(gs.InputDevice.KeySpace) or gs.GetKeyboard().WasPressed(gs.InputDevice.KeyUp):
			if playery + player_height >= BASEY - 1:
				return

		# player y shift
		if playery + player_height < BASEY - 1:
			playery += min(player_vel_y, BASEY - playery - player_height)

		# player velocity change
		if player_vel_y < 15:
			player_vel_y += player_acc_y

		# draw sprites
		sprite2dtex(IMAGES['background'], 0, 0)

		for u_pipe, l_pipe in zip(upper_pipes, lower_pipes):
			sprite2dtex(IMAGES['pipe'][0], u_pipe['x'], u_pipe['y'])
			sprite2dtex(IMAGES['pipe'][1], l_pipe['x'], l_pipe['y'])

		sprite2dtex(IMAGES['base'], basex, BASEY)
		show_score(score)
		sprite2dtex(IMAGES['player'][1], playerx,playery)

		render.flip()
		clock.update()


def player_oscillate(playerShm):
	"""oscillates the value of playerShm['val'] between 8 and -8"""
	if abs(playerShm['val']) == 8:
		playerShm['dir'] *= -1

	playerShm['val'] += playerShm['dir']


def get_random_pipe():
	"""returns a randomly generated pipe"""
	# y of gap between upper and lower pipe
	gap_y = random.randrange(0, int(BASEY * 0.6 - PIPEGAPSIZE))
	gap_y += int(BASEY * 0.2)
	pipe_height = IMAGES['pipe'][0].GetHeight()
	pipe_x = SCREENWIDTH + 10

	return [
		{'x': pipe_x, 'y': gap_y - pipe_height},  # upper pipe
		{'x': pipe_x, 'y': gap_y + PIPEGAPSIZE}   # lower pipe
	]


def show_score(score):
	"""displays score in center of screen"""
	score_digits = [int(x) for x in list(str(score))]
	total_width = 0 # total width of all numbers to be printed

	for digit in score_digits:
 		total_width += IMAGES['numbers'][digit].GetWidth()

	x_offset = (SCREENWIDTH - total_width) / 2

	for digit in score_digits:
		sprite2dtex(IMAGES['numbers'][digit], x_offset, SCREENHEIGHT * 0.1)
		x_offset += IMAGES['numbers'][digit].GetWidth()


def check_collision(player, upper_pipes, lower_pipes):
	"""returns True if player collders with base or pipes."""
	pi = player['index']
	player['w'] = IMAGES['player'][0].GetWidth()
	player['h'] = IMAGES['player'][0].GetHeight()

	# if player crashes into ground
	if player['y'] + player['h'] >= BASEY - 1:
		return [True, True]
	else:   

		player_rect = gs.iRect.FromWidthHeight(player['x'], player['y'],
					  player['w'], player['h'])
		pipeW = IMAGES['pipe'][0].GetWidth()
		pipeH = IMAGES['pipe'][0].GetHeight()

		for u_pipe, l_pipe in zip(upper_pipes, lower_pipes):
			# upper and lower pipe rects
			uPipeRect = gs.iRect.FromWidthHeight(int(u_pipe['x']), u_pipe['y'], pipeW, pipeH)
			lPipeRect = gs.iRect.FromWidthHeight(int(l_pipe['x']), l_pipe['y'], pipeW, pipeH)

			# player and upper/lower pipe hitmasks
			pHitMask = HITMASKS['player'][pi]
			uHitmask = HITMASKS['pipe'][0]
			lHitmask = HITMASKS['pipe'][1]

			# if bird collided with upipe or lpipe
			uCollide = check_pixel_collision(player_rect, uPipeRect, pHitMask, uHitmask)
			lCollide = check_pixel_collision(player_rect, lPipeRect, pHitMask, lHitmask)

			if uCollide or lCollide:
				return [True, False]

	return [False, False]


def check_pixel_collision(rect1, rect2, hitmask1, hitmask2):
	"""Checks if two objects collide and not just their rects"""
	rect = rect1.Intersection(rect2)

	if rect.GetWidth() == 0 or rect.GetHeight() == 0:
		return False

	x1, y1 = rect.sx - rect1.sx, rect.sy - rect1.sy
	x2, y2 = rect.sx - rect2.sx, rect.sy - rect2.sy

	def get_hitmask_value(mask, x, y):
		if x < 0 or y < 0 or x >= len(mask) or y >= len(mask[x]):
			return False
		return mask[x][y]

	for x in range(0, rect.GetWidth(), 2):
		for y in range(0, rect.GetHeight(), 2):
			if get_hitmask_value(hitmask1, x1+x, y1+y) and get_hitmask_value(hitmask2, x2+x, y2+y):
				return True
	return False


def get_bitmap_hitmask(tex):
	"""returns a hitmask using an image's alpha."""
	pic = gs.Picture()
	render.get_renderer().CaptureTexture(tex, pic)

	mask = []
	for x in range(pic.GetWidth()):
		mask.append([])
		for y in range(pic.GetHeight()):
			mask[x].append(pic.GetPixelRGBA(x, y).w != 0)
	return mask

if __name__ == '__main__':
	main()
