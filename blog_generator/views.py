from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from .models import BlogPost
from pytube import YouTube
import json
import os
import shutil
import assemblyai as aai
from langchain_community.llms import HuggingFaceHub
from langchain.prompts import PromptTemplate
# Create your views here.


@login_required
def index(request):
    return render(request, 'index.html')


@csrf_exempt
def generate_blog(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            youtubelink = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        # get youtube title
        title = youtube_title(youtubelink)
        # get transcript
        transcription = get_transcription(youtubelink)
        if not transcription:
            return JsonResponse({"error": "Failed to get transcript"},
                                tatus=500)
        # use llm to generate blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error': 'Empty blog generated'},
                                status=500)
        # save blog article to databse
        new_blog_articule = BlogPost.objects.create(user=request.user,
                                                    youtube_title=title,
                                                    youtube_link=youtubelink,
                                                    generated_content=blog_content
                                                    )
        new_blog_articule.save()
        delete_mp3_file()
        # return blog artcile as a response
        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)


def youtube_title(link):
    youtube = YouTube(link)
    title = youtube.title
    return title


def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = "5b0f421a5aa24ae3a7606d1396caba3f"
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    return transcript.text


def generate_blog_from_transcription(transcription):
    llm = HuggingFaceHub(
                repo_id="mistralai/MixTraL-8x7B-Instruct-v0.1",
                model_kwargs={
                    "temperature": 0.12,
                    "max_length": 5000,
                    "max_new_tokens": 1024,
                },
                huggingfacehub_api_token="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"
            )

    prompt_template = PromptTemplate(
                template="""Make me an blog article like an professionelle of the field with only the follow transcription @Transcription: {transcription} @BlogPost:""",
                input_variables=["transcription"],
            )

    model_input = {"transcription": transcription}

    response = llm(
                prompt_template.format(**model_input)
            ).split("@BlogPost:")
    content = response[-1].strip()
    return content


def download_audio(link):
    youtube = YouTube(link)
    video = youtube.streams.filter(only_audio=True).first()
    out_file = video.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file


def delete_mp3_file():
    try:
        shutil.rmtree(settings.MEDIA_ROOT)
    except OSError as e:
        return JsonResponse({'error': f"{settings.MEDIA_ROOT} doesn't exist {e}"},
                            status=500)

    os.makedirs(settings.MEDIA_ROOT)


def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-detail.html', {"blog_article_detail": blog_article_detail})
    else:
        return redirect('/')


def blog_list(request):
    blog_articules = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blog.html",
                  {"blog_articules": blog_articules})


def user_login(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(request,
                            username=username,
                            password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid Username or Password"
            return render(request, 'login.html', {"error_message": error_message})
    return render(request, 'login.html')


def user_signup(request):
    error_message = None
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]
        repeatpassword = request.POST["repeatpassword"]

        if password == repeatpassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = "Error creating account"
                return render(
                              request, 'signup.html',
                              {'error_message': error_message}
                              )
        else:
            error_message = "Password do not match"
    return render(request, 'signup.html', {'error_message': error_message})


def user_logout(request):
    logout(request)
    return redirect('/')
