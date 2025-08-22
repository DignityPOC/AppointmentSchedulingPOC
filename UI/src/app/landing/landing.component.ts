import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';
import { MatIconModule } from '@angular/material/icon'; 
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [CommonModule, RouterModule, MatIconModule],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.scss'
})
export class LandingComponent {
 services = [
    {
      icon: '❤️', // Heart emoji for Cardiology
      title: 'Cardiology',
      description: 'Comprehensive heart care and cardiovascular treatments.',
    },
    {
      icon: '🎗️', // Awareness ribbon for Cancer
      title: 'Oncology',
      description: 'Cancer diagnosis, chemotherapy, and support services.',
    },
    {
      icon: '🧠', // Brain emoji for Neurology
      title: 'Neurology',
      description: 'Diagnosis and treatment of nervous system disorders.',
    },
    {
      icon: '👶', // Baby emoji for Pediatrics
      title: 'Pediatrics',
      description: 'Healthcare services for infants, children, and adolescents.',
    }
  ];
}
