from django import forms
from .models import Feedback


class FeedbackForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 6)],
        widget=forms.RadioSelect,
        label='Rating (1 = Poor, 5 = Excellent)'
    )

    class Meta:
        model  = Feedback
        fields = ['rating', 'comment']
        widgets = {'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Share your experience (optional)'})}
