import datetime
from sqlalchemy.orm.exc import NoResultFound

import discord
from discord.ext import commands


import utils
from config import config, messages
from features import verification
from repository import user_repo
from repository.database import database, session
from repository.database.verification import Valid_person, Permit
from repository.database.year_increment import User_backup

user_r = user_repo.UserRepository()

config = config.Config
messages = messages.Messages
arcas_time = (datetime.datetime.utcnow() -
              datetime.timedelta(hours=config.arcas_delay))


class FitWide(commands.Cog):
    def __init__(self, bot):
        self._bot = bot
        self._guild = self._bot.get_guild(config.guild_id)

        self.bit_names = ["0BIT", "1BIT", "2BIT", "3BIT", "4BIT+"]
        self.mit_names = ["0MIT", "1MIT", "2MIT", "3MIT+"]
        self.other_roles = ["Verify", "Host", "Bot", "Poradce", "Dropout"]
        self.muni_role = ["MUNI"]

        all_roles = self.bit_names + self.mit_names + self.other_roles + self.muni_role

        self._roles = {role: self._get_role(role) for role in all_roles}

        self.verification = verification.Verification(bot, user_r)

    def _get_role(self, name):
        """Gets guild role for FitWide guild
        :param name: {str} role name
        :return: guild role data
        """
        return self._guild.get(self._guild.roles, name=name)
    
    def _get_channel(self, name):
        """Gets guild channel for FitWide guild
        :param name: {str} channel name
        :return: channel data
        """
        return self._guild.get(self._guild.channels, name=name)
    
    @property
    def _guild_members(self):
        return self._guild.members

    def _is_verified(self, member, exclude_muni=False):
        """Check whether a guild member is verified
        :param member: member to be checked
        :param exclude_muni: {bool} also returns False if MUNI role is present
        :return: {bool} False if unverified, True if verified
        """
        roles = member.roles

        if self._roles["verify"] not in roles:
            return False

        unverified_roles = self.other_roles

        if exclude_muni:
            unverified_roles.extend(self.muni_role)

        for role in self.other_roles:
            if self._roles[role] in roles:
                return False

        return True

    async def is_admin(ctx):
        return ctx.author.id == config.admin_id

    async def is_in_modroom(ctx):
        return ctx.message.channel.id == config.mod_room

    @commands.Cog.listener()
    async def on_typing(self, channel, user, when):
        global arcas_time
        if arcas_time + datetime.timedelta(hours=config.arcas_delay) <\
           when and config.arcas_id == user.id:
            arcas_time = when
            gif = discord.Embed()
            gif.set_image(url="https://i.imgur.com/v2ueHcl.gif")
            await channel.send(embed=gif)

    @commands.cooldown(rate=2, per=20.0, type=commands.BucketType.user)
    @commands.check(is_admin)
    @commands.command()
    async def role_check(self, ctx, p_verified: bool = True,
                         p_move: bool = True, p_status: bool = True,
                         p_role: bool = True, p_muni: bool = True):

        verified_members = [m for m in self._guild_members if self._is_verified(m, not p_muni)]

        permited = session.query(Permit)
        permited_ids = [int(person.discord_ID) for person in permited]

        year_roles = {key: value for key, value in self._roles if key in self.bit_names + self.mit_names}

        for member in verified_members:
            if member.id not in permited_ids:
                if p_verified:
                    await ctx.send("Nenasel jsem v verified databazi: " +
                                   utils.generate_mention(member.id))
            else:
                try:
                    login = session.query(Permit).\
                        filter(Permit.discord_ID == str(member.id)).one().login

                    person = session.query(Valid_person).\
                        filter(Valid_person.login == login).one()
                except NoResultFound:
                    continue

                if person.status != 0:
                    if p_status:
                        await ctx.send("Status nesedi u: " + login)

                year = self.verification.transform_year(person.year)

                correct_role = self._roles[year]

                if year is not None and correct_role not in member.roles:
                    if p_move:
                        for role_name, role in year_roles.items():
                            if role in member.roles:
                                await member.add_roles(correct_role)
                                await member.remove_roles(role)
                                await ctx.send("Presouvam: " + member.display_name +
                                               " z " + role_name + " do "+ year)
                                break
                    elif p_role:
                        await ctx.send("Nesedi mi role u: " +
                                       utils.generate_mention(member.id) +
                                       ", mel by mit roli: " + year)
                elif year is None:
                    if p_move:
                        for role_name, role in year_roles.items():
                            if role in member.roles:
                                await member.add_roles(self._roles["dropout"])
                                await member.remove_roles(role)
                                await ctx.send("Presouvam: " + member.display_name +
                                               " z " + role_name + " do dropout")
                                break
                    elif p_role:
                        await ctx.send("Nesedi mi role u: " +
                                       utils.generate_mention(member.id) +
                                       ", ma ted rocnik: " + person.year)

        await ctx.send("Done")

    @commands.cooldown(rate=2, per=20.0, type=commands.BucketType.user)
    @commands.check(is_admin)
    @commands.command()
    async def increment_roles(self, ctx):
        database.base.metadata.create_all(database.db)

        BIT = [self._get_role(role_name) for role_name in self.bit_names]
        MIT = [self._get_role(role_name) for role_name in self.mit_names]

        # pridat kazdeho 3BIT a 2MIT cloveka do DB pred tim nez je jebnem do
        # 4BIT+ respektive 3MIT+ role kvuli rollbacku
        session.query(User_backup).delete()

        for member in BIT[3].members:
            session.add(User_backup(member_ID=member.id))
        for member in MIT[2].members:
            session.add(User_backup(member_ID=member.id))

        session.commit()

        for member in BIT[3].members:
            await member.add_roles(BIT[4])
        for member in MIT[2].members:
            await member.add_roles(MIT[3])

        BIT_colors = [role.color for role in BIT]
        await BIT[3].delete()
        await BIT[2].edit(name="3BIT", color=BIT_colors[3])
        await BIT[1].edit(name="2BIT", color=BIT_colors[2])
        await BIT[0].edit(name="1BIT", color=BIT_colors[1])
        bit0 = await self._guild.create_role(name='0BIT', color=BIT_colors[0])
        await bit0.edit(position=BIT[0].position - 1)

        MIT_colors = [role.color for role in MIT]
        await MIT[2].delete()
        await MIT[1].edit(name="2MIT", color=MIT_colors[2])
        await MIT[0].edit(name="1MIT", color=MIT_colors[1])
        mit0 = await self._guild.create_role(name='0MIT', color=MIT_colors[0])
        await mit0.edit(position=MIT[0].position - 1)

        general_names = [str(x) + "bit-general" for x in range(4)]
        terminy_names = [str(x) + "bit-terminy" for x in range(1, 3)]

        general_channels = [self._get_channel(channel_name)
                            for channel_name in general_names]

        terminy_channels = [self._get_channel(channel_name)
                            for channel_name in terminy_names]
        # TODO: do smth about 4bit general next year, delete it in the meantime
        bit4_general = self._get_channel("4bit-general")
        if bit4_general is not None:
            await bit4_general.delete()

        # move names
        await general_channels[3].edit(name="4bit-general")
        await general_channels[2].edit(name="3bit-general")
        await general_channels[1].edit(name="2bit-general")
        await general_channels[0].edit(name="1bit-general")
        # create 0bit-general
        overwrites = {
            self._guild.default_role:
                discord.PermissionOverwrite(read_messages=False), self._roles["0BIT"]:
                discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        await self._guild.create_text_channel(
                '0bit-general', overwrites=overwrites,
                category=general_channels[0].category,
                position=general_channels[0].position - 1
        )

        # delete 3bit-terminy
        await self._get_channel("3bit-terminy").delete()

        await terminy_channels[1].edit(name="3bit-terminy")
        await terminy_channels[0].edit(name="2bit-terminy")
        # create 1bit-terminy
        overwrites = {
            self._guild.default_role:
                discord.PermissionOverwrite(read_messages=False), self._roles["1BIT"]:
                discord.PermissionOverwrite(read_messages=True, send_messages=False)
        }
        await self._guild.create_text_channel(
                '1bit-terminy', overwrites=overwrites,
                category=terminy_channels[0].category,
                position=terminy_channels[0].position - 1
        )

        # give 4bit perms to the new 3bit terminy
        await terminy_channels[1].set_permissions(self._roles["4BIT+"],
              read_messages=True, send_messages=False
        )

        # Give people the correct mandatory classes after increment
        semester_names = ["{}. Semestr".format(x) for x in range(1, 6)]

        semester = [discord.utils.get(self._guild.categories, name=semester_name)
                    for semester_name in semester_names]

        await semester[0].set_permissions(self._roles["1BIT"],
                                          read_messages=True,
                                          send_messages=True)
        await semester[0].set_permissions(self._roles["2BIT"], overwrite=None)
        await semester[1].set_permissions(self._roles["1BIT"],
                                          read_messages=True,
                                          send_messages=True)
        await semester[1].set_permissions(self._roles["2BIT"], overwrite=None)
        await semester[2].set_permissions(self._roles["2BIT"],
                                          read_messages=True,
                                          send_messages=True)
        await semester[2].set_permissions(self._roles["3BIT"], overwrite=None)
        await semester[3].set_permissions(self._roles["2BIT"],
                                          read_messages=True,
                                          send_messages=True)
        await semester[3].set_permissions(self._roles["3BIT"], overwrite=None)
        await semester[4].set_permissions(self._roles["3BIT"],
                                          read_messages=True,
                                          send_messages=True)

        await ctx.send('Holy fuck, vsechno se povedlo, '
                       'tak zase za rok <:Cauec:602052606210211850>')

    # TODO: the opposite of increment_roles (for rollback and testing)
    # and role_check to check if peoples roles match the database

    @commands.cooldown(rate=2, per=20.0, type=commands.BucketType.user)
    @commands.check(is_in_modroom)
    @commands.command()
    async def update_db(self, ctx):
        with open("merlin-latest", "r") as f:
            data = f.readlines()

        new_people = []
        new_logins = []

        for line in data:
            line = line.split(":")
            login = line[0]
            name = line[4].split(",", 1)[0]
            try:
                year = line[4].split(",")[1]
            except IndexError:
                continue
            new_people.append(Valid_person(login=login, year=year,
                                           name=name))
            new_logins.append(login)

        for person in new_people:
            session.merge(person)

        for person in session.query(Valid_person):
            if person.login not in new_logins:
                try:
                    # check for muni
                    int(person.login)
                    person.year = "MUNI"
                except ValueError:
                    person.year = "dropout"

        session.commit()

        await ctx.send("Update databaze probehl uspesne")


    @commands.cooldown(rate=2, per=20.0, type=commands.BucketType.user)
    @commands.check(is_in_modroom)
    @commands.command()
    async def get_users_login(self, ctx, member: discord.Member):
        result = session.query(Permit).\
            filter(Permit.discord_ID == str(member.id)).one_or_none()

        if result is None:
            await ctx.send("Neni v DB prej")
        else:
            await ctx.send(result.login)
        

    @commands.cooldown(rate=2, per=20.0, type=commands.BucketType.user)
    @commands.check(is_in_modroom)
    @commands.command()
    async def get_logins_user(self, ctx, login):
        result = session.query(Permit).\
            filter(Permit.login == login).one_or_none()

        if result is None:
            await ctx.send("Neni na serveru prej")
        else:
            await ctx.send(utils.generate_mention(result.discord_ID))

    @commands.cooldown(rate=2, per=20.0, type=commands.BucketType.user)
    @commands.check(is_in_modroom)
    @commands.command()
    async def reset_login(self, ctx, login):

        result = session.query(Valid_person).\
            filter(Valid_person.login == login).one_or_none()
        if result is None:
            await ctx.send("Neni validni login pre")
        else:
            session.query(Permit).\
                filter(Permit.login == login).delete()
            result.status = 1
            session.commit()
            await ctx.send("Done")

    @commands.cooldown(rate=2, per=20.0, type=commands.BucketType.user)
    @commands.check(is_in_modroom)
    @commands.command()
    async def connect_login_to_user(self, ctx, login, member: discord.Member):

        result = session.query(Valid_person).\
            filter(Valid_person.login == login).one_or_none()
        if result is None:
            await ctx.send("Neni validni login prej")
        else:
            session.add(Permit(login=login, discord_ID=str(member.id)))
            result.status = 0
            session.commit()
            await ctx.send("Done")

    @get_users_login.error
    @reset_login.error
    @get_logins_user.error
    @role_check.error
    @increment_roles.error
    @update_db.error
    async def fitwide_checks_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send('Nothing to see here comrade. ' + 
                           '<:KKomrade:484470873001164817>')

def setup(bot):
    bot.add_cog(FitWide(bot))
