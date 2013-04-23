import hashlib
import re
from random import shuffle
from math import ceil

import web
from web import form


web.config.debug = False

urls = (
    '/', 'Index',
    '/login', 'Login',
    '/logout', 'Logout',
    '/([0-9]{3})', 'User',
    '/photo/([0-9]{3})', 'Photo',
    '/register', 'Register',
    '/profile', 'Profile',
    '/delete', 'Delete'
)

app = web.application(urls, globals())

session = web.session.Session(app, web.session.DiskStore('sessions'),
                              initializer={'login': 0})

db = web.database(dbn='mysql', db='message_board', user='root')


def get_users():
    result = list(db.select('users', what='id_,username'))
    shuffle(result)
    return result

def get_messages(id_):
    return db.select('user_'+id_, order='created desc')

def get_name(id_):
    return db.select('users', what='username', where='id_=$id_',
                     vars=locals())[0].username

render = web.template.render('templates', base='layout',
                             globals={'get_users': get_users,
                                      'hasattr': hasattr,
                                      'session': session,
                                      'get_name': get_name,
                                      'get_messages': get_messages,
                                      'ceil': ceil})


def authenticate(id_=None, username=None, passwd=None):
    try:
        if id_:
            ident = db.select('users', where='id_=$id_', what='id_,pass',
                              vars=locals())[0]
        elif username:
            ident = db.select('users', where='username=$username',
                              what='id_,pass', vars=locals())[0]
    except IndexError:
        pass
    else:
        if hashlib.sha1('sAlT754-'+passwd).hexdigest() == ident['pass']:
            session.login = 1
            session.id_ = ident.id_
            return True

    return False


def loadcookie():
    try:
        id_, passwd = web.cookies().id_, web.cookies().passwd
    except AttributeError:
        pass
    else:
        authenticate(id_=id_, passwd=passwd)

app.add_processor(web.loadhook(loadcookie))


class Index:
    def GET(self):
        if session.login:
            raise web.seeother('/' + session.id_)
        else:
            raise web.seeother('/login')


login_form = form.Form(
    form.Textbox('username', description='Username'),
    form.Password('passwd', description='Password'),
    form.Checkbox('remember_me', value=1, description='Remember Me'),
    form.Button('login', type='submit', description='Login'),
    validators=[form.Validator('Incorrect username and password combination',
                               lambda i: authenticate(username=i.username,
                                                      passwd=i.passwd))]
)

class Login:
    def GET(self):
        f = login_form()
        return render.login(f)

    def POST(self):
        f = login_form()
        if f.validates():
            if f.remember_me.get_value():
                web.setcookie('id_', session.id_, 86400)
                web.setcookie('passwd', f.passwd.value, 86400)
            raise web.seeother('/' + session.id_)
        else:
            return render.login(f)


class Logout:
    def GET(self):
        session.login = 0
        session.kill()
        web.setcookie('id_', None)
        web.setcookie('passwd', None)
        raise web.seeother('/login')


message_form = form.Form(
    form.Textarea('message', rows=5, cols=75,
                   description='Leave your message'),
    form.Button('submit', type='submit', description='Submit'),
    validators=[form.Validator('Please login first.', lambda i: session.login)]
)

class User:
    def GET(self, id_):
        try:
            information = db.select('users', where='id_=$id_',
                                    vars=locals())[0];
        except IndexError:
            return render.user_does_not_exist()
        else:
            page = int(web.input(page=1).page)
            return render.user(information, message_form(), page)

    def POST(self, id_):
        f = message_form()
        if f.validates():
            message = f.message.value
            if message:
                db.insert('user_'+id_, user_id=session.id_, message=message)
            raise web.seeother('/' + id_)
        else:
            try:
                information = db.select('users', where='id_=$id_',
                                        vars=locals())[0];
            except IndexError:
                return render.user_does_not_exist()
            else:
                return render.user(information, f, 1)


class Photo:
    def GET(self, id_):
        user = db.select('users', where='id_=$id_', what='photo',
                         vars=locals())
        if len(user) == 1:
            return user[0].photo
        else:
            return render.user_does_not_exist()


vusername = form.regexp(r'[a-zA-Z0-9]{1,15}',
                        'Must be less than 15 characters.')
vpass = form.regexp(r'.{6,}', 'Must be at least 6 characters.')
vemail= form.regexp(r'.+@.+', 'Please type in a correct email address.')
register_form = form.Form(
    form.Textbox('username', vusername, description='Username'),
    form.Password('passwd', vpass, description='Password'),
    form.Password('passwd2', description='Repeat password'),
    form.Textbox('first_name', description='First Name'),
    form.Textbox('last_name', description='Last Name'),
    form.Textbox('email', vemail, description='Email'),
    form.Radio('gender', args=('Male', 'Female'), description='Gender'),
    form.Textbox('school', description='School'),
    form.Textbox('address', description='Address'),
    form.Dropdown('birth_year', args=map(str, range(1900, 2014)), value=2013,
                  description='Birth Year'),
    form.Dropdown('birth_month', args=map(str, range(1, 13)),
                  description='Birth Month'),
    form.Dropdown('birth_day', args=map(str, range(1, 32)),
                  description='Birth Day'),
    form.Textarea('summary', description='Summary'),
    form.File('photo', description='Photo'),
    form.Button('submit', type='submit', description='Submit'),
    validators=[form.Validator("Password did't match",
                               lambda i: i.passwd == i.passwd2)]
)

fields = ['username', 'first_name', 'last_name', 'email', 'gender', 'school',
          'address', 'birth_year', 'birth_month', 'birth_day', 'summary',
          'photo']

class Register:
    def GET(self):
        f = register_form()
        return render.register(f)

    def POST(self):
        f = register_form()
        if not f.validates():
            return render.register(f)
        else:
            vars_ = {field: f[field].value for field in fields}
            id_ = db.query('select count(*) as total from users')[0].total + 1
            vars_['id_'] = '%03d' % id_
            vars_['pass'] = hashlib.sha1('sAlT754-'+f.passwd.value).hexdigest()
            db.insert('users', **vars_)
            db.query('create table user_%s (user_id char(3), message longtext,\
                       created timestamp default now())' % vars_['id_'])
            authenticate(id_=vars_['id_'], passwd=f.passwd.value)
            return render.register_ok(vars_['id_'])


profile_form = form.Form(
    form.Textbox('username', vusername, description='Username'),
    form.Textbox('first_name', description='First Name'),
    form.Textbox('last_name', description='Last Name'),
    form.Textbox('email', vemail, description='Email'),
    form.Radio('gender', args=('Male', 'Female'), description='Gender'),
    form.Textbox('school', description='School'),
    form.Textbox('address', description='Address'),
    form.Dropdown('birth_year', args=map(str, range(1900, 2014)),
                  description='Birth Year'),
    form.Dropdown('birth_month', args=map(str, range(1, 13)),
                  description='Birth Month'),
    form.Dropdown('birth_day', args=map(str, range(1, 32)),
                  description='Birth Day'),
    form.Textarea('summary', description='Summary'),
    form.File('photo', description='Photo'),

    form.Password('old_passwd',
        form.Validator('Wrong old password',
            lambda p: authenticate(id_=session.id_, passwd=p) if p else True),
        description='Old password'),
    form.Password('passwd', description='Password'),
    form.Password('passwd2', description='Repeat password'),

    form.Button('submit', type='submit', description='Submit'),
    validators=[form.Validator('The password must be at least 6 characters.',
                    lambda i: len(i.passwd) > 5 if i.old_passwd else True),
                form.Validator("Password did't match",
                    lambda i: i.passwd == i.passwd2 if i.old_passwd else True)]
)

class Profile:
    def GET(self):
        if not session.login:
            raise web.seeother('/login')
        else:
            f = profile_form()
            ident = db.select('users', where='id_=$id_',
                              vars=dict(id_=session.id_))[0]
            for field in fields[0:-1]:
                f[field].value = ident[field]
            return render.profile(f)

    def POST(self):
        if not session.login:
            raise web.seeother('/login')
        else:
            f = profile_form()
            if not f.validates():
                return render.profile(f)
            else:
                vars_ = {field: f[field].value for field in fields[0:-1]}
                if f.photo.value:
                    vars_['photo'] = f.photo.value
                if f.passwd.value:
                    vars_['pass'] = hashlib.sha1('sAlT754-'+f.passwd.value) \
                                                                   .hexdigest()
                db.update('users', where='id_=$id_',
                          vars=dict(id_=session.id_), **vars_)
                return render.profile_ok()


class Delete:
    def GET(self):
        referer = web.ctx.env.get('HTTP_REFERER', '/')
        m = re.match(r'http://.*/([0-9]{3}).*', referer)
        if m:
            page = m.group(1)
            try:
                user, created = web.input().user, web.input().created
            except AttributeError:
                pass
            else:
                if session.login:
                    if session.id_ == page or session.id_ == user:
                        db.delete('user_'+page, where='created=$created',
                                  vars=locals())

        raise web.seeother(referer)


if __name__ == '__main__':
    app.run()
