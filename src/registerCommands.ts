import { REST } from '@discordjs/rest';
import { Routes, ApplicationCommandOptionType } from 'discord-api-types/v10';

export async function registerCommands() {
	const token = process.env.TOKEN;
	const clientId = process.env.CLIENT_ID;
	const guildId = process.env.GUILD_ID;

	if (!token || !clientId) {
		console.warn('⚠️ Missing TOKEN or CLIENT_ID environment variables. Skipping slash command registration.');
		return;
	}

	const commands = [
		{
			name: 'complete-quests',
			description: 'Scan and automatically complete all active Discord quests for a user token',
			options: [
				{
					name: 'token',
					description: 'Your Discord account user token',
					type: ApplicationCommandOptionType.String,
					required: true,
				},
			],
		},
	];

	const rest = new REST({ version: '10' }).setToken(token);

	try {
		console.log('Started refreshing application (/) commands...');
		if (guildId) {
			await rest.put(
				Routes.applicationGuildCommands(clientId, guildId),
				{ body: commands },
			);
			console.log(`✅ Registered slash command (/complete-quests token:...) for Guild ID: ${guildId}`);
		} else {
			await rest.put(
				Routes.applicationCommands(clientId),
				{ body: commands },
			);
			console.log('✅ Registered slash command (/complete-quests token:...) globally.');
		}
	} catch (error) {
		console.error('❌ Error registering slash commands:', error);
	}
}

if (require.main === module) {
	registerCommands();
}
