# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, redirect
from forms import SignUpForm, LoginForm, PostForm, LikeForm, CommentForm
from models import UserModel, SessionToken, PostModel, LikeModel, CommentModel
from django.contrib.auth.hashers import make_password, check_password
from datetime import timedelta
from django.utils import timezone
from mysite.settings import BASE_DIR
import requests
from clarifai.rest import ClarifaiApp, Image as CImage
from imgurpython import ImgurClient
from enum import Enum
import sendgrid
from sendgrid.helpers.mail import *
import os


def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            # saving data to DB
            user = UserModel(name=name, password=make_password(password), email=email, username=username)
            user.save()
            return render(request, 'success.html')
            # return redirect('login/')
    else:
        form = SignUpForm()

    return render(request, 'index.html', {'form': form})


def login_view(request):
    response_data = {}
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = UserModel.objects.filter(username=username).first()

            if user:
                if check_password(password, user.password):
                    token = SessionToken(user=user)
                    token.create_token()
                    token.save()
                    response = redirect('feed/')
                    response.set_cookie(key='session_token', value=token.session_token)
                    return response
                else:
                    response_data['message'] = 'Incorrect Password! Please try again!'

    elif request.method == 'GET':
        form = LoginForm()

    response_data['form'] = form
    return render(request, 'login.html', response_data)


def post_view(request):
    user = check_validation(request)

    if user:
        if request.method == 'POST':
            form = PostForm(request.POST, request.FILES)
            if form.is_valid():
                image = form.cleaned_data.get('image')
                caption = form.cleaned_data.get('caption')
                post = PostModel(user=user, image=image, caption=caption)
                post.save()
                apikey = 'lBzto9IhYQnI8Z6kd4dFap0gGbFexBgRBknxuISGFK4'
                request_url = ('https://apis.paralleldots.com/sentiment?sentence1=%s&apikey=%s') % (caption, apikey)
                print 'POST request url : %s' % (request_url)
                sentiment = requests.get(request_url, verify=False).json()
                sentiment_value = sentiment['sentiment']

                path = str(BASE_DIR + '\\' + post.image.url)

                client = ImgurClient("315c0833408f9c0", "ab94bfdc68d430ac6f7aa5f16260b1f5d6e27b5e")
                post.image_url = client.upload_from_path(path, anon=True)['link']
                print post.image_url
                post.save()
                keywords = ['garbage', 'waste', 'trash', 'dirt', 'pollution', 'dust']
                value_list = []
                app = ClarifaiApp(api_key='ecc5aea7265040b4b320b3446f96152c')

                model = app.models.get('general-v1.3')
                image = CImage(url=post.image_url)
                prediction = model.predict([image])

                for i in range(0, len(prediction['outputs'][0]['data']['concepts'])):
                    if prediction['outputs'][0]['data']['concepts'][i]['name'] in keywords:
                        value = prediction['outputs'][0]['data']['concepts'][i]['value']
                        value_list.append(value)

                if (sentiment_value < 0.6 and max(value_list) > 0.8):
                    print 'dirty image'
                    send_mail(post.image_url)

                return redirect('/feed/')

        else:
            form = PostForm()
        return render(request, 'post.html', {'form': form})
    else:
        return redirect('/login/')


def send_mail(url):
    sg = sendgrid.SendGridAPIClient(apikey='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')

    from_email = Email("sakshikhattar1@gmail.com")
    to_email = Email("Raman007bidhuri@gmail.com")
    message = "<html><body><h1>Image of the dirty area</h1><br><img src =" + url + "></body></html>"
    subject = "Image of dirty area!"
    content = Content("text/html", message)
    mail = Mail(from_email, subject, to_email, content)
    response = sg.client.mail.send.post(request_body=mail.get())
    print(response.status_code)
    print(response.body)
    print(response.headers)


def feed_view(request):
    user = check_validation(request)
    if user:

        posts = PostModel.objects.all().order_by('created_on')

        for post in posts:
            existing_like = LikeModel.objects.filter(post_id=post.id, user=user).first()
            if existing_like:
                post.has_liked = True

        return render(request, 'feed.html', {'posts': posts})
    else:

        return redirect('/login/')


def like_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = LikeForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            existing_like = LikeModel.objects.filter(post_id=post_id, user=user).first()
            if not existing_like:
                LikeModel.objects.create(post_id=post_id, user=user)
            else:
                existing_like.delete()
            return redirect('/feed/')
    else:
        return redirect('/login/')


def comment_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            comment_text = form.cleaned_data.get('comment_text')
            comment = CommentModel.objects.create(user=user, post_id=post_id, comment_text=comment_text)
            comment.save()
            return redirect('/feed/')
        else:
            return redirect('/feed/')
    else:
        return redirect('/login')

def logout_view(request):
    user = check_validation(request)
    if user is not None:
        latest_session = SessionToken.objects.filter(user=user).last()
        if latest_session:
            latest_session.delete()

    return redirect("/login/")


# For validating the session
def check_validation(request):
    if request.COOKIES.get('session_token'):
        session = SessionToken.objects.filter(session_token=request.COOKIES.get('session_token')).first()
        if session:
            time_to_live = session.created_on + timedelta(days=1)
            if time_to_live > timezone.now():
                return session.user
    else:
        return None