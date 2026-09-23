from django import forms
from django.contrib.auth.models import User
from .models import UserProfile
from django.core.exceptions import ValidationError
import re
from .models import Address

class SignupForm(forms.Form):

    first_name = forms.CharField(max_length=30,required=True, widget=forms.TextInput(attrs={'placeholder': 'First Name','class': 'form-control'}))
    last_name = forms.CharField(max_length=30,required=True,widget=forms.TextInput(attrs={'placeholder': 'Last Name','class': 'form-control'}))
    email = forms.EmailField(required=True,widget=forms.EmailInput(attrs={'placeholder': 'Email Address','class': 'form-control'}))
    password1 = forms.CharField(label='New Password',widget=forms.PasswordInput(attrs={'placeholder': 'Enter New Password','class': 'form-control'}))
    password2 = forms.CharField(label='Confirm Password',widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password','class': 'form-control'}))
    phone = forms.CharField(max_length=15,required=True,widget=forms.TextInput(attrs={'placeholder': 'Phone Number','class': 'form-control'}))
    
    class Meta:
        model = User
        fields = ['first_name','last_name','email','password1','password2','phone']


    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name").strip()

        if not re.match(r'^[A-Za-z ]+$', first_name):
            raise ValidationError("First name can contain only letters and spaces.")

        return first_name
    
     
    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name").strip()

        if not re.match(r'^[A-Za-z ]+$', last_name):
            raise ValidationError("Last name can contain only letters and spaces.")

        return last_name
    
    
    def clean_password1(self):

        password1 = self.cleaned_data.get('password1')

        if len(password1) < 8:
            raise ValidationError(
                "Password must be at least 8 characters long."
            )

        if not re.search(r'[A-Z]', password1):
            raise ValidationError(
                "Password must contain at least one uppercase letter."
            )

        if not re.search(r'[a-z]', password1):
            raise ValidationError(
                "Password must contain at least one lowercase letter."
            )

        if not re.search(r'[0-9]', password1):
            raise ValidationError(
                "Password must contain at least one number."
            )

        if not re.search(
            r'[!@#$%^&*(),.?\":{}|<>]',
            password1
        ):
            raise ValidationError(
                "Password must contain at least one special character."
            )

        return password1


    
    def clean(self):

        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2:
            if password1 != password2:
                self.add_error(
                    "password2",
                    "Passwords do not match."
                )

        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get("email").strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email is already registered.")

        return email

    def clean_phone(self):
        phone = re.sub(r"\D", "", self.cleaned_data.get("phone", ""))

        if not phone.isdigit():
            raise ValidationError("Phone number should contain only digits.")

        if len(phone) != 10:
            raise ValidationError("Phone number must contain exactly 10 digits.")

        if not re.match(r"^[6-9]\d{9}$", phone):
            raise ValidationError(
                "Please enter a valid mobile number starting with 6, 7, 8, or 9."
            )

        if UserProfile.objects.filter(phone=phone).exists():
            raise ValidationError("This mobile number is already registered.")

        return phone


class OTPVerificationForm(forms.Form):
    otp = forms.CharField(label="OTP",max_length=6,min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter 6-digit OTP",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
            }
        ),
    )

    def clean_otp(self):
        otp = self.cleaned_data["otp"].strip()
        if not otp.isdigit():
            raise forms.ValidationError("OTP must contain only digits.")
        if len(otp) != 6:
            raise forms.ValidationError("OTP must be exactly 6 digits.")
        return otp


class ResetPasswordForm(forms.Form):

    new_password = forms.CharField(label="New Password",widget=forms.PasswordInput(
            attrs={
                "placeholder": "Enter new password",
                "class": "form-control",
                "autocomplete": "new-password"
            }
        )
    )

    confirm_password = forms.CharField(label="Confirm Password",widget=forms.PasswordInput(
            attrs={
                "placeholder": "Confirm new password",
                "class": "form-control",
                "autocomplete": "new-password"
            }
        )
    )

    def clean_new_password(self):

        password = self.cleaned_data.get("new_password")

        if len(password) < 8:
            raise ValidationError(
                "Password must be at least 8 characters long."
            )

        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                "Password must contain at least one uppercase letter."
            )

        if not re.search(r'[a-z]', password):
            raise ValidationError(
                "Password must contain at least one lowercase letter."
            )

        if not re.search(r'[0-9]', password):
            raise ValidationError(
                "Password must contain at least one number."
            )

        if not re.search(
            r'[!@#$%^&*(),.?\":{}|<>]',
            password
        ):
            raise ValidationError(
                "Password must contain at least one special character."
            )

        return password


    def clean(self):

        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2:
            if password1 != password2:
                self.add_error(
                    "password2",
                    "Passwords do not match."
                )

        return cleaned_data


class EditProfileForm(forms.Form):

    first_name = forms.CharField(max_length=150,required=True,widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150,required=True,widget=forms.TextInput(attrs={'class': 'form-control',}))
    email = forms.EmailField(required=True,widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone = forms.CharField( max_length=15,required=True,widget=forms.TextInput(attrs={'class': 'form-control','maxlength': '10'}))
    profile_image = forms.ImageField(required=False,widget=forms.FileInput(attrs={'class': 'form-control','id': 'profile-image-input','accept': 'image/*'}))

    def __init__(self, *args, **kwargs):

        self.user = kwargs.pop('user', None)

        super().__init__(*args, **kwargs)

        if self.user:

            self.fields['first_name'].initial = (
                self.user.first_name
            )

            self.fields['last_name'].initial = (
                self.user.last_name
            )

            self.fields['email'].initial = (
                self.user.email
            )

            if hasattr(self.user, 'profile'):

                self.fields['phone'].initial = (
                    self.user.profile.phone
                )

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        if not first_name:
            raise forms.ValidationError(
                'First name is required.'
            )
        if len(first_name) < 2:
            raise forms.ValidationError(
                'First name must contain at least 2 characters.'
            )
        if not first_name.replace(' ', '').isalpha():
            raise forms.ValidationError(
                'First name can contain only letters.'
            )

        return first_name

    def clean_last_name(self):

        last_name = self.cleaned_data.get('last_name', '').strip()

        if not last_name:
            raise forms.ValidationError(
                'Last name is required.'
            )

        if len(last_name) < 2:
            raise forms.ValidationError(
                'Last name must contain at least 2 characters.'
            )

        if not last_name.replace(' ', '').isalpha():
            raise forms.ValidationError(
                'Last name can contain only letters.'
            )

        return last_name

    def clean_email(self):

        email = self.cleaned_data.get(
            'email',
            ''
        ).strip().lower()

        if not email:
            raise forms.ValidationError(
                'Email address is required.'
            )

        try:
            local_part, domain = email.split('@')
        except ValueError:
            raise forms.ValidationError(
                'Please enter a valid email address.'
            )

        if not any(
            char.isalnum()
            for char in local_part
        ):
            raise forms.ValidationError(
                'Please enter a valid email address.'
            )

        if not local_part[0].isalnum():
            raise forms.ValidationError(
                'Email must start with a letter or number.'
            )

        if not local_part[-1].isalnum():
            raise forms.ValidationError(
                'Email must end with a letter or number before @.'
            )

        if '.' not in domain:
            raise forms.ValidationError(
                'Please enter a valid email domain.'
            )

        existing_user = User.objects.filter(
            email__iexact=email
        ).first()

        if existing_user:
            if (
                not self.user
                or existing_user.id != self.user.id
            ):
                raise forms.ValidationError(
                    'This email address is already registered.'
                )

        return email


    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise forms.ValidationError(
                'Phone number is required.'
            )

        if not phone.isdigit():
            raise forms.ValidationError(
                'Phone number must contain only digits.'
            )

        if len(phone) != 10:
            raise forms.ValidationError(
                'Phone number must contain exactly 10 digits.'
            )

        if phone[0] not in '6789':
            raise forms.ValidationError(
                'Please enter a valid phone number.'
            )
        current_user = getattr(self, 'user', None)

        existing_profile = UserProfile.objects.filter(
            phone=phone
        ).first()
        if existing_profile:
            if (
                not current_user
                or existing_profile.user_id != current_user.id
            ):
                raise forms.ValidationError(
                    'This phone number is already registered.'
                )

        return phone

    def clean_profile_image(self):

        image = self.cleaned_data.get('profile_image')
        if not image:
            return image
        if image.size > 2 * 1024 * 1024:
            raise forms.ValidationError(
                'Profile image must be smaller than 2 MB.'
            )
        allowed_types = [
            'image/jpeg',
            'image/png',
            'image/webp',
        ]

        if image.content_type not in allowed_types:
            raise forms.ValidationError(
                'Only JPG, PNG and WEBP images are allowed.'
            )

        return image


class AddressForm(forms.ModelForm):

    address_type = forms.ChoiceField(
        choices=Address.ADDRESS_TYPE_CHOICES,
        widget=forms.RadioSelect,
        required=True
    )

    class Meta:
        model = Address

        fields = [
            'country',
            'pincode',
            'address_type',
            'building',
            'area',
            'landmark',
            'city',
            'state',
            'is_default',
        ]

        widgets = {
            'country': forms.TextInput(
                attrs={
                    'placeholder': 'Enter country or region',
                    'maxlength': '100',
                }
            ),

            'pincode': forms.TextInput(
                attrs={
                    'placeholder': 'Enter pincode',
                    'maxlength': '6',
                    'inputmode': 'numeric',
                }
            ),

            'building': forms.TextInput(
                attrs={
                    'placeholder': 'Enter flat, house number or building',
                    'maxlength': '255',
                }
            ),

            'area': forms.TextInput(
                attrs={
                    'placeholder': 'Enter area, street, sector or village',
                    'maxlength': '255',
                }
            ),

            'landmark': forms.TextInput(
                attrs={
                    'placeholder': 'Enter landmark (optional)',
                    'maxlength': '255',
                }
            ),

            'city': forms.TextInput(
                attrs={
                    'placeholder': 'Enter city',
                    'maxlength': '100',
                }
            ),

            'state': forms.TextInput(
                attrs={
                    'placeholder': 'Enter state',
                    'maxlength': '100',
                }
            ),

            'is_default': forms.CheckboxInput(
                attrs={
                    'class': 'default-checkbox',
                }
            ),
        }

    

    def clean_country(self):

        country = self.cleaned_data.get(
            'country',
            ''
        ).strip()

        if not country:
            raise forms.ValidationError(
                'Country is required.'
            )

        if len(country) < 2:
            raise forms.ValidationError(
                'Country must contain at least 2 characters.'
            )

        
        if not re.fullmatch(
            r'[A-Za-z ]+',
            country
        ):
            raise forms.ValidationError(
                'Country can contain only letters.'
            )

        return country



    def clean_pincode(self):

        pincode = self.cleaned_data.get(
            'pincode',
            ''
        ).strip()

        if not pincode:
            raise forms.ValidationError(
                'Pincode is required.'
            )

        if not pincode.isdigit():
            raise forms.ValidationError(
                'Pincode must contain only numbers.'
            )

        if len(pincode) != 6:
            raise forms.ValidationError(
                'Pincode must be exactly 6 digits.'
            )

        return pincode


   

    def clean_building(self):

        building = self.cleaned_data.get(
            'building',
            ''
        ).strip()

        if not building:
            raise forms.ValidationError(
                'Building or house number is required.'
            )

        if len(building) < 2:
            raise forms.ValidationError(
                'Building must contain at least 2 characters.'
            )

       
        if not re.fullmatch(
            r'[A-Za-z0-9\s,\-./#]+',
            building
        ):
            raise forms.ValidationError(
                'Building contains invalid characters.'
            )

        return building


    

    def clean_area(self):

        area = self.cleaned_data.get(
            'area',
            ''
        ).strip()

        if not area:
            raise forms.ValidationError(
                'Area is required.'
            )

        if len(area) < 2:
            raise forms.ValidationError(
                'Area must contain at least 2 characters.'
            )

       
        if not re.search(
            r'[A-Za-z]',
            area
        ):
            raise forms.ValidationError(
                'Area must contain letters.'
            )

        if not re.fullmatch(
            r'[A-Za-z0-9\s,\-./#]+',
            area
        ):
            raise forms.ValidationError(
                'Area contains invalid characters.'
            )

        return area



    def clean_landmark(self):

        landmark = self.cleaned_data.get(
            'landmark',
            ''
        ).strip()

        
        if not landmark:
            return ''

        if len(landmark) < 2:
            raise forms.ValidationError(
                'Landmark must contain at least 2 characters.'
            )

        
        if not re.search(
            r'[A-Za-z]',
            landmark
        ):
            raise forms.ValidationError(
                'Landmark must contain letters.'
            )

        if not re.fullmatch(
            r'[A-Za-z0-9\s,\-./#]+',
            landmark
        ):
            raise forms.ValidationError(
                'Landmark contains invalid characters.'
            )

        return landmark


   

    def clean_city(self):

        city = self.cleaned_data.get(
            'city',
            ''
        ).strip()

        if not city:
            raise forms.ValidationError(
                'City is required.'
            )

        if len(city) < 2:
            raise forms.ValidationError(
                'City must contain at least 2 characters.'
            )

        if not re.fullmatch(
            r'[A-Za-z ]+',
            city
        ):
            raise forms.ValidationError(
                'City can contain only letters.'
            )

        return city

    

    def clean_state(self):

        state = self.cleaned_data.get(
            'state',
            ''
        ).strip()

        if not state:
            raise forms.ValidationError(
                'State is required.'
            )

        if len(state) < 2:
            raise forms.ValidationError(
                'State must contain at least 2 characters.'
            )

        if not re.fullmatch(
            r'[A-Za-z ]+',
            state
        ):
            raise forms.ValidationError(
                'State can contain only letters.'
            )

        return state


class ChangePasswordForm(forms.Form):

    current_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter current password",
                "autocomplete": "current-password",
            }
        ),
    )

    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter new password",
                "autocomplete": "new-password",
            }
        ),
    )

    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm new password",
                "autocomplete": "new-password",
            }
        ),
    )


    def __init__(self, *args, user=None, **kwargs):

        super().__init__(*args, **kwargs)

        self.user = user

    def clean_current_password(self):

        current_password = self.cleaned_data.get(
            "current_password"
        )

        if not current_password:
            raise forms.ValidationError(
                "Please enter your current password."
            )

        if self.user and not self.user.check_password(
            current_password
        ):
            raise forms.ValidationError(
                "Current password is incorrect."
            )

        return current_password




    def clean_new_password(self):

        new_password = self.cleaned_data.get(
            "new_password"
        )

        if not new_password:
            raise forms.ValidationError(
                "Please enter a new password."
            )

        if len(new_password) < 8:

            raise forms.ValidationError(
                "Password must be at least 8 characters long."
            )

        if len(new_password) > 128:

            raise forms.ValidationError(
                "Password cannot be longer than 128 characters."
            )

        if any(char.isspace() for char in new_password):

            raise forms.ValidationError(
                "Password cannot contain spaces."
            )

        if not any(
            char.isupper()
            for char in new_password
        ):

            raise forms.ValidationError(
                "Password must contain at least one uppercase letter."
            )

        if not any(
            char.islower()
            for char in new_password
        ):

            raise forms.ValidationError(
                "Password must contain at least one lowercase letter."
            )

        if not any(
            char.isdigit()
            for char in new_password
        ):

            raise forms.ValidationError(
                "Password must contain at least one number."
            )

        if not any(
            not char.isalnum()
            for char in new_password
        ):

            raise forms.ValidationError(
                "Password must contain at least one special character."
            )

        if self.user:

            current_password = (
                self.data.get("current_password")
            )

            if current_password and (
                new_password == current_password
            ):

                raise forms.ValidationError(
                    "New password must be different from your current password."
                )


        return new_password

    def clean_confirm_password(self):

        confirm_password = self.cleaned_data.get(
            "confirm_password"
        )

        if not confirm_password:

            raise forms.ValidationError(
                "Please confirm your new password."
            )

        return confirm_password

    def clean(self):

        cleaned_data = super().clean()

        new_password = cleaned_data.get(
            "new_password"
        )

        confirm_password = cleaned_data.get(
            "confirm_password"
        )


        if (
            new_password
            and confirm_password
            and new_password != confirm_password
        ):

            self.add_error(
                "confirm_password",
                "Passwords do not match."
            )


        return cleaned_data