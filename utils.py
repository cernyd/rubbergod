import git
from discord import Member
from config import config, messages


def generate_mention(user_id):
    return '<@' + str(user_id) + '>'


def git_hash():
    repo = git.Repo(search_parent_directories=True)
    return repo.head.object.hexsha


def git_commit_msg():
    repo = git.Repo(search_parent_directories=True)
    return repo.head.commit.message


def git_pull():
    repo = git.Repo(search_parent_directories=True)
    cmd = repo.git
    return cmd.pull()


def str_emoji_id(emoji):
    if isinstance(emoji, int):
        return str(emoji)

    return emoji if isinstance(emoji, str) else str(emoji.id)


def has_role(user, role_name: str):
    if type(user) != Member:
        return None

    return role_name.lower() in [x.name.lower() for x in user.roles]


def permission_check():
    def wrapper(command):
        async def wrapped(ctx, *args, **kwargs):

            if ctx.author.id == config.admin_id:
                return await command(ctx, *args, **kwargs)

            else:  # Unauthorized response
                await ctx.send(fill_message("insufficient_rights", user=ctx.author.id))
        return wrapped
    return wrapper


def fill_message(message_name, **kwargs):
    if 'user' in kwargs:
        kwargs['user'] = generate_mention(kwargs['user'])

    if 'toaster' in kwargs:
        kwargs['toaster'] = generate_mention(kwargs['toaster'])
    
    try:
        template = getattr(messages, message_name)
        template.format(**kwargs)
    except Exception:
        return ""
