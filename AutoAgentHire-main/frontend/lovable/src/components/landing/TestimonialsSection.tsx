import { motion } from "framer-motion";
import { Star, Quote } from "lucide-react";

interface TestimonialCardProps {
  quote: string;
  name: string;
  role: string;
  rating: number;
  delay?: number;
}

const TestimonialCard = ({ quote, name, role, rating, delay = 0 }: TestimonialCardProps) => (
  <motion.div
    initial={{ opacity: 0, y: 30 }}
    whileInView={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5, delay }}
    viewport={{ once: true }}
    className="relative p-8 rounded-2xl bg-card/60 backdrop-blur-xl border border-white/10 hover:border-primary/30 transition-all duration-300"
  >
    <Quote className="absolute top-6 right-6 w-8 h-8 text-primary/20" />
    
    <div className="flex gap-1 mb-4">
      {Array.from({ length: rating }).map((_, i) => (
        <Star key={i} className="w-5 h-5 fill-warning text-warning" />
      ))}
    </div>

    <p className="text-foreground/90 leading-relaxed mb-6 italic">"{quote}"</p>

    <div className="flex items-center gap-4">
      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-blue-400 flex items-center justify-center text-primary-foreground font-semibold">
        {name.charAt(0)}
      </div>
      <div>
        <div className="font-semibold text-foreground">{name}</div>
        <div className="text-sm text-muted-foreground">{role}</div>
      </div>
    </div>
  </motion.div>
);

const testimonials = [
  {
    quote: "AutoAgentHire completely changed my job search. I landed 3 interviews in the first week without lifting a finger!",
    name: "Sarah Chen",
    role: "Software Engineer",
    rating: 5,
  },
  {
    quote: "The AI cover letters are incredible. They're personalized and professional - way better than what I could write myself.",
    name: "Marcus Johnson",
    role: "Product Manager",
    rating: 5,
  },
  {
    quote: "I was skeptical at first, but this tool saved me hours every day. The automated applications are a game-changer.",
    name: "Emily Rodriguez",
    role: "Data Analyst",
    rating: 5,
  },
];

export const TestimonialsSection = () => {
  return (
    <section className="py-24 px-4 relative">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            What Our <span className="gradient-text">Users Say</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Join thousands of job seekers who've transformed their career search.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {testimonials.map((testimonial, index) => (
            <TestimonialCard key={testimonial.name} {...testimonial} delay={index * 0.1} />
          ))}
        </div>
      </div>
    </section>
  );
};
