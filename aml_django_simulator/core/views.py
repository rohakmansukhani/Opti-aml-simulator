from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json

def index(request):
    if request.user.is_authenticated:
        if check_data():
            return redirect('dashboard')
    
    return render(request, 'index.html', {
        'is_authenticated': request.user.is_authenticated
    })

def user_login(request):
    if request.method == 'POST':
        # Retrieve form data
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Simplified Logic: Universal Password
        if password == "admin":
            from django.contrib.auth.models import User
            # Ensure we have a default user to attach the session to
            user, _ = User.objects.get_or_create(username='admin', defaults={'email': 'admin@optimoney.com'})
            login(request, user)
            return redirect('index')
            
        # If failed, redirect back to index (could add message logic later)
        return redirect('index')
    return redirect('index')

def user_logout(request):
    logout(request)
    return redirect('index')

@login_required(login_url='index')
def dashboard(request):
    if not check_data():
        return redirect('index')
    return render(request, 'dashboard/home.html')

@login_required(login_url='index')
def builder(request):
    if not check_data():
        return redirect('index')
    return render(request, 'dashboard/builder.html')

@login_required(login_url='index')
def reports(request):
    if not check_data():
        return redirect('index')
    return render(request, 'dashboard/reports.html')

@login_required(login_url='index')
def comparison(request):
    if not check_data():
        return redirect('index')
    return render(request, 'dashboard/compare.html')

@login_required(login_url='index')
def scenarios(request):
    if not check_data():
        return redirect('index')
    return render(request, 'dashboard/scenarios.html')

@login_required(login_url='index')
def database(request):
    if not check_data():
        return redirect('index')
    return render(request, 'dashboard/database.html')

def check_data():
    from simulation.models import Transaction
    return Transaction.objects.exists()
