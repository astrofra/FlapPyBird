from itertools import cycle
import random
import sys

import gs
import gs.plus.render as render
import gs.plus.clock as clock

FPS = 30
SCREENWIDTH  = 288
SCREENHEIGHT = 512
# amount by which base can maximum shift to left
PIPEGAPSIZE  = 100 # gap between upper and lower part of pipe
BASEY        = SCREENHEIGHT * 0.79
# image, sound and hitmask  dicts
IMAGES, SOUNDS, HITMASKS = {}, {}, {}

# list of all possible players (tuple of 3 positions of flap)
PLAYERS_LIST = (
	# red bird
	(
		'@assets/sprites/redbird-upflap.png',
		'@assets/sprites/redbird-midflap.png',
		'@assets/sprites/redbird-downflap.png',
	),
	# blue bird
	(
		# amount by which base can maximum shift to left
		'@assets/sprites/bluebird-upflap.png',
		'@assets/sprites/bluebird-midflap.png',
		'@assets/sprites/bluebird-downflap.png',
	),
	# yellow bird
	(
		'@assets/sprites/yellowbird-upflap.png',
		'@assets/sprites/yellowbird-midflap.png',
		'@assets/sprites/yellowbird-downflap.png',
	),
)

# list of backgrounds
BACKGROUNDS_LIST = (
	'@assets/sprites/background-day.png',
	'@assets/sprites/background-night.png',
)

# list of pipes
PIPES_LIST = (
	'@assets/sprites/pipe-green.png',
	'@assets/sprites/pipe-red.png',
)


# ------------------------------------------------------------------------------
def sprite2dtex(tex, x: float, y: float, size: float = 1.0, color=gs.Color.White, pivot_x: float = 0.5,
			 pivot_y: float = 0.5, flip_h: bool = False, flip_v: bool = False):
	x -= size * pivot_x
	y -= size * pivot_y

	render.texture2d(x, y, size, tex, color, flip_h, not flip_v)


def main():
	global al, keyboard #, SCREEN, FPSCLOCK

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

	# FPSCLOCK = pygame.time.Clock()
	# SCREEN = pygame.display.set_mode((SCREENWIDTH, SCREENHEIGHT))
	# pygame.display.set_caption('Flappy Bird')

	# numbers sprites for score display
	IMAGES['numbers'] = (
		render.get_renderer().LoadTexture('@assets/sprites/0.png'), #.convert_alpha(),
		render.get_renderer().LoadTexture('@assets/sprites/1.png'), #.convert_alpha(),
		render.get_renderer().LoadTexture('@assets/sprites/2.png'), #.convert_alpha(),
		render.get_renderer().LoadTexture('@assets/sprites/3.png'), #.convert_alpha(),
		render.get_renderer().LoadTexture('@assets/sprites/4.png'), #.convert_alpha(),
		render.get_renderer().LoadTexture('@assets/sprites/5.png'), #.convert_alpha(),
		render.get_renderer().LoadTexture('@assets/sprites/6.png'), #.convert_alpha(),
		render.get_renderer().LoadTexture('@assets/sprites/7.png'), #.convert_alpha(),
		render.get_renderer().LoadTexture('@assets/sprites/8.png'), #.convert_alpha(),
		render.get_renderer().LoadTexture('@assets/sprites/9.png') #.convert_alpha()
	)

	# game over sprite
	IMAGES['gameover'] = render.get_renderer().LoadTexture('@assets/sprites/gameover.png') #.convert_alpha()
	# message sprite for welcome screen
	IMAGES['message'] = render.get_renderer().LoadTexture('@assets/sprites/message.png') #.convert_alpha()
	# base (ground) sprite
	IMAGES['base'] = render.get_renderer().LoadTexture('@assets/sprites/base.png') #.convert_alpha()

	# sounds
	sound_ext = '.wav'

	SOUNDS['die'] = al.LoadSound('@assets/audio/die' + sound_ext)
	SOUNDS['hit'] = al.LoadSound('@assets/audio/hit' + sound_ext)
	SOUNDS['point'] = al.LoadSound('@assets/audio/point' + sound_ext)
	SOUNDS['swoosh'] = al.LoadSound('@assets/audio/swoosh' + sound_ext)
	SOUNDS['wing'] = al.LoadSound('@assets/audio/wing' + sound_ext)

	while True:
		# select random background sprites
		rand_bg = random.randint(0, len(BACKGROUNDS_LIST) - 1)
		IMAGES['background'] = render.get_renderer().LoadTexture(BACKGROUNDS_LIST[rand_bg]) #.convert()

		# select random player sprites
		rand_player = random.randint(0, len(PLAYERS_LIST) - 1)
		IMAGES['player'] = (
			render.get_renderer().LoadTexture(PLAYERS_LIST[rand_player][0]), #.convert_alpha(),
			render.get_renderer().LoadTexture(PLAYERS_LIST[rand_player][1]), #.convert_alpha(),
			render.get_renderer().LoadTexture(PLAYERS_LIST[rand_player][2]) #.convert_alpha(),
		)

		# select random pipe sprites
		pipe_index = random.randint(0, len(PIPES_LIST) - 1)
		pipe_image = render.get_renderer().LoadTexture(PIPES_LIST[pipe_index])
		IMAGES['pipe'] = (
			pipe_image, # gs.Picture.BlitTransform(pipe_image, pipe_image.GetRect(), gs.RotationMatrixXAxis(math.pi), gs.Filter.Bilinear),
			pipe_image
		)

		# hismask for pipes
		HITMASKS['pipe'] = (
			getHitmask(IMAGES['pipe'][0]),
			getHitmask(IMAGES['pipe'][1]),
		)

		# hitmask for player
		HITMASKS['player'] = (
			getHitmask(IMAGES['player'][0]),
			getHitmask(IMAGES['player'][1]),
			getHitmask(IMAGES['player'][2]),
		)

		movement_info = showWelcomeAnimation()
		crash_info = mainGame(movement_info)
		showGameOverScreen(crash_info)


def showWelcomeAnimation():
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
	player_shm_vals = {'val': 0, 'dir': 1}

	while True:
		clock.update()
		render.clear()

		render.set_blend_mode2d(render.BlendAlpha)

		# for event in pygame.event.get():
		if keyboard.WasPressed(gs.InputDevice.KeyEscape):
			# pygame.quit()
			sys.exit()
		if keyboard.WasPressed(gs.InputDevice.KeySpace):
			# make first flap sound and return values for mainGame
			al.Start(SOUNDS['wing'])
			return {
				'playery': playery + player_shm_vals['val'],
				'basex': basex,
				'player_index_gen': player_index_gen,
			}

		# adjust playery, player_index, basex
		if (loop_iter + 1) % 5 == 0:
			player_index = next(player_index_gen)
		loop_iter = (loop_iter + 1) % 30
		basex = -((-basex + 4) % base_shift)
		playerShm(player_shm_vals)

		# draw sprites
		sprite2dtex(IMAGES['background'], 0, 0)
		sprite2dtex(IMAGES['player'][player_index],
					playerx, playery + player_shm_vals['val'])
		sprite2dtex(IMAGES['message'], messagex, messagey)
		sprite2dtex(IMAGES['base'], basex, BASEY)

		render.set_blend_mode2d(render.BlendOpaque)

		render.flip()


def mainGame(movement_info):
	score = player_index = loop_iter = 0
	player_index_gen = movement_info['player_index_gen']
	playerx, playery = int(SCREENWIDTH * 0.2), movement_info['playery']

	basex = movement_info['basex']
	base_shift = IMAGES['base'].GetWidth() - IMAGES['background'].GetWidth()

	# get 2 new pipes to add to upper_pipes lower_pipes list
	new_pipe_1 = getRandomPipe()
	new_pipe_2 = getRandomPipe()

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
	player_min_vel_y =  -8   # min vel along Y, max ascend speed
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
		crash_test = checkCrash({'x': playerx, 'y': playery, 'index': player_index},
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
			new_pipe = getRandomPipe()
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
		showScore(score)
		sprite2dtex(IMAGES['player'][player_index], playerx, playery)

		render.flip()
		clock.update()


def showGameOverScreen(crash_info):
	"""crashes the player down ans shows gameover image"""
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
		showScore(score)
		sprite2dtex(IMAGES['player'][1], playerx,playery)

		render.flip()
		clock.update()


def playerShm(playerShm):
	"""oscillates the value of playerShm['val'] between 8 and -8"""
	if abs(playerShm['val']) == 8:
		playerShm['dir'] *= -1

	if playerShm['dir'] == 1:
		playerShm['val'] += 1
	else:
		playerShm['val'] -= 1


def getRandomPipe():
	"""returns a randomly generated pipe"""
	# y of gap between upper and lower pipe
	gap_y = random.randrange(0, int(BASEY * 0.6 - PIPEGAPSIZE))
	gap_y += int(BASEY * 0.2)
	pipe_height = IMAGES['pipe'][0].GetHeight()
	pipeX = SCREENWIDTH + 10

	return [
		{'x': pipeX, 'y': gap_y - pipe_height},  # upper pipe
		{'x': pipeX, 'y': gap_y + PIPEGAPSIZE}, # lower pipe
	]


def showScore(score):
	"""displays score in center of screen"""
	scoreDigits = [int(x) for x in list(str(score))]
	totalWidth = 0 # total width of all numbers to be printed

	for digit in scoreDigits:
		totalWidth += IMAGES['numbers'][digit].GetWidth()

	Xoffset = (SCREENWIDTH - totalWidth) / 2

	for digit in scoreDigits:
		sprite2dtex(IMAGES['numbers'][digit], Xoffset, SCREENHEIGHT * 0.1)
		Xoffset += IMAGES['numbers'][digit].GetWidth()


def checkCrash(player, upper_pipes, lower_pipes):
	"""returns True if player collders with base or pipes."""
	pi = player['index']
	player['w'] = IMAGES['player'][0].GetWidth()
	player['h'] = IMAGES['player'][0].GetHeight()

	# if player crashes into ground
	if player['y'] + player['h'] >= BASEY - 1:
		return [True, True]
	else:

		playerRect = gs.iRect.FromWidthHeight(player['x'], player['y'],
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
			uCollide = pixelCollision(playerRect, uPipeRect, pHitMask, uHitmask)
			lCollide = pixelCollision(playerRect, lPipeRect, pHitMask, lHitmask)

			if uCollide or lCollide:
				return [True, False]

	return [False, False]


def pixelCollision(rect1, rect2, hitmask1, hitmask2):
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

	for x in range(rect.GetWidth()):
		for y in range(rect.GetHeight()):
			if get_hitmask_value(hitmask1, x1+x, y1+y) and get_hitmask_value(hitmask2, x2+x, y2+y):
				return True
	return False


def getHitmask(tex):
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
