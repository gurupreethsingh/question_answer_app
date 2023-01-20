from flask import Flask, render_template, g, request, session, redirect, url_for
from database import get_db
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

def get_current_user():
    user_result = None

    if 'user' in session:
        user = session['user']

        db = get_db()
        user_cur = db.execute('select id, name, password, expert, admin from users where name = ?', [user])
        user_result = user_cur.fetchone()

    return user_result

@app.route('/')
def index():
    user = get_current_user()
    # fquery to show all the questions and answers in the home page.
    db = get_db()
    question_cur = db.execute('select questions.id as question_id, questions.question_text, askers.name as asker_name, experts.name as expert_name from questions join users as askers  on askers.id= questions.asked_by_id join users as experts on  experts.id = questions.expert_id where questions.answer_text is not null' )
    questions_result = question_cur.fetchall()
    # now pass the questions_result into the home page to view in home.html page
    return render_template('home.html', user=user, questions = questions_result)

@app.route('/register', methods=['GET', 'POST'])
def register():
    user = get_current_user()
    if request.method == 'POST':
        db = get_db()
        # checking for same usersname already exists or not 
        existing_user_cur = db.execute('select id from users where name = ?', [request.form['name']])
        existing_user = existing_user_cur.fetchone()
        if existing_user:
            return render_template('register.html', user = user, error = 'Username already taken, Try different username.') # we will show this error message in the register.html page. if username is already in db.

        hashed_password = generate_password_hash(request.form['password'], method='sha256')
        db.execute('insert into users (name, password, expert, admin) values (?, ?, ?, ?)', [request.form['name'], hashed_password, '0', '0'])
        db.commit()
        session['user'] = request.form['name']
        return redirect(url_for('index'))
    return render_template('register.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    user = get_current_user()
    error = None
    if request.method == 'POST':
        db = get_db()
        name = request.form['name']
        password = request.form['password']
        user_cur = db.execute('select id, name, password from users where name = ?', [name])
        user_result = user_cur.fetchone()

        if user_result:
            if check_password_hash(user_result['password'], password):
                session['user'] = user_result['name']
                return redirect(url_for('index'))
            else:
                error = 'Username or password did not match. Try again.'
    else:
        error = 'Username or password did not match. Try again.'
    return render_template('login.html', user=user , error = error)

@app.route('/question<question_id>')
def question(question_id):
    user = get_current_user()
    db = get_db()
    # query to show all the ansered questions and who asked them and who answered them.
    question_cur = db.execute('select questions.question_text, questions.answer_text,  askers.name as asker_name, experts.name as expert_name from questions join users as askers  on askers.id= questions.asked_by_id join users as experts on  experts.id = questions.expert_id where questions.id = ?', [question_id] )
    question = question_cur.fetchone()
    # pass this question into the question.html template
    return render_template('question.html', user=user, question = question)

@app.route('/answer/<question_id>' , methods = ["POST", "GET"])
def answer(question_id):
    user = get_current_user()
    # to answer the questions for experts they have to be logged in . or go to login page.
    if not user:
        return redirect(url_for('login'))

    if user['expert'] == 0:
        return redirect(url_for('index')) # only experts can answer the questions. 

    db = get_db()
    if request.method == 'POST':
        # store the answer given by the expert into the database by doing an update query. 
        db.execute('update questions set answer_text = ? where id = ?', [request.form['answer'], question_id])
        db.commit()
        return redirect(url_for('unanswered'))

    # get the question asked by the student and show it in the answer.html page to answer. 
    question_cur =  db.execute('select id,  question_text from questions where id = ?',[question_id])
    question = question_cur.fetchone()
    return render_template('answer.html', user=user, question=question)
     # now show this question_asked in the answer.html page. 


@app.route('/ask',  methods = ["POST", "GET"])
def ask():
    user = get_current_user()
    # only logged in user can ask the questions. else navigate to login page.
    if not user:
        return redirect(url_for('login'))

    db = get_db()
    if request.method == 'POST':
        # we will insert the question asked by the user and the expert persons name in the questions table.
        db.execute('insert into questions (question_text, asked_by_id, expert_id) values (?, ?, ?)',
         [request.form['question'], user['id'], request.form['expert']])
        db.commit()
        return redirect(url_for('index'))   # functions name for the first page. 
    # get all the expert users from the database and show them in ask.html page.. 
    expert_cur = db.execute('select * from users where expert = 1')
    all_experts = expert_cur.fetchall()
    return render_template('ask.html', user=user, all_experts = all_experts)

@app.route('/unanswered')
def unanswered():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    # get all the questions which are unanwered, means answer_text is null,  from the database, questions table.

    if user['expert'] == 0:
        return redirect(url_for('index')) # only experts can see the unanswered questions. 
    db = get_db()
    question_cur = db.execute('select questions.id, questions.question_text, users.name from questions join users on  users.id = questions.asked_by_id  where  questions.answer_text is null and questions.expert_id = ?', [user['id']])
    all_questions = question_cur.fetchall()
    return render_template('unanswered.html', user=user, questions = all_questions)

@app.route('/users')
def users():
    user = get_current_user()

    if not user:
        return redirect(url_for('login'))  # if there is not user logged in it will navigte to login page.

    if user['admin'] == 0:
        return redirect(url_for('index'))  # if he is not admin then no user setup page for him.

    db = get_db()
    users_cur = db.execute('select id, name, expert, admin from users')
    users_results = users_cur.fetchall()

    return render_template('users.html', user=user, users=users_results)

@app.route('/promote/<user_id>')
def promote(user_id):
    user = get_current_user()

    if not user:
        return redirect(url_for('login'))

    if user['admin'] == 0:
        return redirect(url_for('index'))  # if he is not admin then no update setup page for him.

    db = get_db()
    db.execute('update users set expert = 1 where id = ?', [user_id])
    db.commit()
    
    return redirect(url_for('users'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)